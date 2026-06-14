from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from content.models import LearningModule, Question


def render_module_viewer(module: LearningModule) -> None:
    # Sidebar table of contents
    with st.sidebar:
        st.title("Contents")
        for i, et in enumerate(module.topics):
            if st.button(f"{i + 1}. {et.topic.title}", key=f"toc_{i}", use_container_width=True):
                st.session_state.selected_topic = i

    selected = st.session_state.get("selected_topic", 0)

    st.title(module.title)
    st.caption(f"{len(module.topics)} topics")

    for i, et in enumerate(module.topics):
        with st.expander(
            f"{'▶' if i == selected else '▸'} {i + 1}. {et.topic.title}",
            expanded=(i == selected),
        ):
            st.markdown(et.content_html)

            if et.key_takeaways:
                st.markdown("**Key Takeaways**")
                for kp in et.key_takeaways:
                    st.markdown(f"- {kp}")

            for diagram in et.diagrams:
                if diagram.diagram_type == "mermaid":
                    _render_mermaid(diagram.content, diagram.caption)
                elif diagram.diagram_type == "extracted_image":
                    try:
                        st.image(diagram.content, caption=diagram.caption or None)
                    except Exception:
                        pass

            if et.inline_questions:
                st.markdown("---")
                st.markdown("**Check your understanding**")
                for q in et.inline_questions:
                    _render_inline_question(q)

    st.divider()
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("Take Quiz →", type="primary"):
            st.session_state.page = "quiz"
            st.rerun()


def _render_mermaid(code: str, caption: str = "") -> None:
    if not code.strip():
        return
    escaped = code.replace("`", "\\`")
    html = f"""
    <div style="background:#fff;border:1px solid #e0e0e0;border-radius:8px;padding:12px;margin:8px 0;">
      <div class="mermaid">{escaped}</div>
      {f'<p style="font-size:0.85em;color:#555;margin-top:6px;">{caption}</p>' if caption else ''}
    </div>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <script>mermaid.initialize({{startOnLoad:true,theme:'default'}});</script>
    """
    components.html(html, height=420, scrolling=True)


def _render_inline_question(q: Question) -> None:
    key_base = f"inlineq_{q.question_id}"
    st.markdown(f"**{q.question_text}**")

    if q.question_type == "single_choice":
        choice = st.radio(
            "Select one:", q.options, key=key_base, index=None, label_visibility="collapsed"
        )
        if choice is not None:
            idx = q.options.index(choice)
            if idx in q.correct_answers:
                st.success(f"Correct! {q.explanation}")
            else:
                st.error(f"Not quite. {q.explanation}")
    else:
        checked: list[int] = []
        for j, opt in enumerate(q.options):
            if st.checkbox(opt, key=f"{key_base}_{j}"):
                checked.append(j)
        if st.button("Check", key=f"{key_base}_btn"):
            if sorted(checked) == sorted(q.correct_answers):
                st.success(f"Correct! {q.explanation}")
            else:
                correct_opts = [q.options[i] for i in q.correct_answers]
                st.error(f"Not quite. Correct: {', '.join(correct_opts)}. {q.explanation}")
