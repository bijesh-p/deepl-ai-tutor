from __future__ import annotations

import streamlit as st
from content.models import LearningModule, Question

try:
    from streamlit_mermaid import st_mermaid
    _HAS_MERMAID = True
except ImportError:
    _HAS_MERMAID = False


def render_module_viewer(module: LearningModule) -> None:
    st.title(module.title)
    st.caption(f"{len(module.topics)} topics")

    # Sidebar table of contents
    with st.sidebar:
        st.markdown("### Contents")
        for et in module.topics:
            st.markdown(f"- {et.topic.title}")

    for et in module.topics:
        with st.expander(f"**{et.topic.title}**", expanded=False):
            st.markdown(et.content_md)

            if et.key_takeaways:
                st.markdown("**Key takeaways:**")
                for kt in et.key_takeaways:
                    st.markdown(f"- {kt}")

            for diagram in et.diagrams:
                if diagram.diagram_type == "mermaid":
                    st.markdown(f"*{diagram.caption}*")
                    if _HAS_MERMAID:
                        st_mermaid(diagram.content)
                    else:
                        st.code(diagram.content, language="text")

            if et.inline_questions:
                st.markdown("---")
                st.markdown("**Check your understanding**")
                _render_inline_questions(et.topic.topic_id, et.inline_questions)

    st.markdown("---")
    if st.button("Take the Quiz", type="primary"):
        st.session_state["page"] = "quiz"
        st.rerun()


def _render_inline_questions(topic_id: str, questions: list[Question]) -> None:
    for i, q in enumerate(questions):
        key = f"inline_{topic_id}_{i}"
        answered_key = f"{key}_answered"

        st.markdown(f"**Q{i + 1}: {q.question_text}**")

        if q.question_type == "single_choice":
            choice = st.radio(
                label="",
                options=q.options,
                index=None,
                key=key,
                label_visibility="collapsed",
            )
            if choice is not None and not st.session_state.get(answered_key):
                selected_idx = q.options.index(choice)
                if selected_idx in q.correct_answers:
                    st.success(f"Correct! {q.explanation}")
                else:
                    correct_text = q.options[q.correct_answers[0]]
                    st.error(f"Not quite. The correct answer is: **{correct_text}**. {q.explanation}")
                st.session_state[answered_key] = True
        else:
            # multiple_choice
            selected = []
            for j, opt in enumerate(q.options):
                if st.checkbox(opt, key=f"{key}_opt_{j}"):
                    selected.append(j)
            if st.button("Check", key=f"{key}_check"):
                if sorted(selected) == sorted(q.correct_answers):
                    st.success(f"Correct! {q.explanation}")
                else:
                    correct_opts = [q.options[idx] for idx in q.correct_answers]
                    st.error(f"Not quite. Correct: **{', '.join(correct_opts)}**. {q.explanation}")
