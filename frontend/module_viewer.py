from __future__ import annotations

import streamlit as st

from content.models import EnrichedTopic, LearningModule, Question


def render_module_viewer(module: LearningModule) -> None:
    st.title(module.title)

    # Sidebar table of contents
    with st.sidebar:
        st.header("Topics")
        for et in module.topics:
            st.markdown(f"- {et.topic.title}")
        st.markdown("---")
        if st.button("Take Quiz →", type="primary", use_container_width=True):
            st.session_state["page"] = "quiz"
            st.rerun()

    for i, et in enumerate(module.topics):
        _render_topic(et, topic_index=i)

    st.markdown("---")
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("Take Quiz →", type="primary"):
            st.session_state["page"] = "quiz"
            st.rerun()


def _render_topic(et: EnrichedTopic, topic_index: int) -> None:
    with st.expander(f"**{et.topic.order}. {et.topic.title}**", expanded=(topic_index == 0)):
        # Summary chip
        st.caption(et.topic.summary)

        # Main content
        st.markdown(et.content_md)

        # Key takeaways
        if et.key_takeaways:
            st.info("**Key Takeaways**\n\n" + "\n".join(f"- {t}" for t in et.key_takeaways))

        # Diagrams
        for diagram in et.diagrams:
            if diagram.diagram_type == "mermaid":
                st.markdown(f"**{diagram.caption}**" if diagram.caption else "")
                st.code(diagram.content, language="mermaid")
            elif diagram.diagram_type == "extracted_image":
                try:
                    st.image(diagram.content, caption=diagram.caption or "")
                except Exception:
                    pass  # Skip broken image paths silently

        # Inline questions
        if et.inline_questions:
            st.markdown("#### Check Your Understanding")
            for q in et.inline_questions:
                _render_inline_question(q, topic_index)


def _render_inline_question(q: Question, topic_index: int) -> None:
    state_key = f"iq_answered_{topic_index}_{q.question_id}"
    answer_key = f"iq_answer_{topic_index}_{q.question_id}"

    st.markdown(f"**{q.question_text}**")
    answered = st.session_state.get(state_key, False)

    if q.question_type == "single_choice":
        options_display = ["(Select an answer)"] + q.options
        selection = st.radio(
            label=q.question_text,
            options=options_display,
            index=0,
            key=f"radio_{topic_index}_{q.question_id}",
            label_visibility="collapsed",
            disabled=answered,
        )
        if selection != "(Select an answer)" and not answered:
            selected_idx = q.options.index(selection)
            is_correct = [selected_idx] == q.correct_answers
            st.session_state[state_key] = True
            st.session_state[answer_key] = (is_correct, q.explanation)

    else:  # multiple_choice
        selections = st.multiselect(
            label=q.question_text,
            options=q.options,
            key=f"multi_{topic_index}_{q.question_id}",
            label_visibility="collapsed",
            disabled=answered,
        )
        if not answered:
            col_check, col_spacer = st.columns([1, 4])
            with col_check:
                if st.button("Check", key=f"check_{topic_index}_{q.question_id}"):
                    selected_idxs = sorted(q.options.index(s) for s in selections)
                    is_correct = selected_idxs == sorted(q.correct_answers)
                    st.session_state[state_key] = True
                    st.session_state[answer_key] = (is_correct, q.explanation)

    if st.session_state.get(state_key):
        is_correct, explanation = st.session_state[answer_key]
        if is_correct:
            st.success(f"Correct! {explanation}")
        else:
            correct_labels = [q.options[i] for i in q.correct_answers]
            st.error(
                f"Not quite. Correct answer: **{', '.join(correct_labels)}**\n\n{explanation}"
            )

    st.markdown("")  # spacing
