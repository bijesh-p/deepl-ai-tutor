from __future__ import annotations

import time
from datetime import datetime, timezone

import streamlit as st
from backend.content.models import LearningModule, Question

try:
    from streamlit_mermaid import st_mermaid
    _HAS_MERMAID = True
except ImportError:
    _HAS_MERMAID = False


def render_module_viewer(module: LearningModule) -> None:
    progress = st.session_state.get("pipeline_progress")
    generating = progress and progress["state"] not in ("completed", "failed", "aborted")

    module = _sync_module_from_progress(module, progress)
    st.session_state["module"] = module

    total_expected = progress["total_topics"] if progress else len(module.topics)
    done_count = len(module.topics)

    st.title(module.title)
    st.caption(f"{done_count}/{total_expected} topics ready" if generating else f"{done_count} topics")

    for et in module.topics:
        with st.expander(f"**{et.topic.title}**", expanded=True):
            if et.top_concepts:
                concepts_text = " | ".join(f"**{c}**" for c in et.top_concepts)
                st.info(f"Top concepts: {concepts_text}")

            if et.audio_path:
                st.audio(et.audio_path, format="audio/mp3")

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

    if generating and progress:
        _pending_topics_fragment()

    st.markdown("---")
    col_quiz, col_tutor = st.columns(2)
    with col_quiz:
        quiz_ready = not generating or (progress and progress.get("bank") is not None)
        if st.button("Take the Quiz", type="primary", disabled=not quiz_ready):
            if progress and progress.get("bank"):
                st.session_state["question_bank"] = progress["bank"]
            st.session_state["page"] = "quiz"
            st.rerun()
        if not quiz_ready:
            st.caption("Available after all topics are generated")
    with col_tutor:
        if st.button("Start Adaptive Tutor"):
            st.session_state["page"] = "tutor_room"
            st.rerun()


def _sync_module_from_progress(module: LearningModule, progress: dict | None) -> LearningModule:
    if not progress:
        return module
    enriched = progress.get("enriched_topics", [])
    if len(enriched) > len(module.topics):
        return LearningModule(
            module_id=progress.get("module_id", module.module_id),
            title=progress.get("doc_title", module.title),
            source_doc_id=progress.get("doc_id", module.source_doc_id),
            topics=list(enriched),
            created_at=module.created_at,
        )
    if progress["state"] == "completed" and progress.get("module"):
        return progress["module"]
    return module


@st.fragment(run_every=3)
def _pending_topics_fragment() -> None:
    progress = st.session_state.get("pipeline_progress")
    if not progress:
        return

    state = progress["state"]
    if state in ("completed", "failed", "aborted"):
        st.rerun()
        return

    current = progress.get("current_topic", "")
    done = progress.get("topics_enriched", 0)
    total = progress.get("total_topics", 0)

    if state == "enriching" and current:
        st.info(f"Generating: {current} ({done}/{total} topics ready)")
    elif state == "quiz":
        st.info("Generating quiz questions...")
    elif state == "saving":
        st.info("Saving module...")


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
