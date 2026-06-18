from __future__ import annotations

import time
from datetime import datetime, timezone

import streamlit as st
from backend.content.diagram_generator import _sanitize_mermaid
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

    col_tutor_top, _ = st.columns([2, 5])
    with col_tutor_top:
        if st.button("🚀 Start Adaptive Tutor", type="primary"):
            st.session_state["page"] = "tutor_room"
            st.rerun()
    st.markdown("---")

    with st.sidebar:
        st.markdown("### Contents")
        for et in module.topics:
            st.markdown(f"- {et.topic.title}")
        if generating and progress:
            pending_topics = progress.get("topics", [])
            enriched_titles = {et.topic.title for et in module.topics}
            for t in pending_topics:
                if t.title not in enriched_titles:
                    st.markdown(f"- *{t.title}* (pending)")

    for et in module.topics:
        with st.expander(f"**{et.topic.title}**", expanded=True):
            if et.top_concepts:
                concepts_text = " | ".join(f"**{c}**" for c in et.top_concepts)
                st.info(f"Top concepts: {concepts_text}")

            if et.audio_path:
                st.audio(et.audio_path, format="audio/mp3")

            # Diagram first (anchor-first), then explanation below
            mermaid_diagrams = [d for d in et.diagrams if d.diagram_type == "mermaid"]
            if mermaid_diagrams:
                for diagram in mermaid_diagrams:
                    st.caption(f"📊 {diagram.caption}")
                    clean = _sanitize_mermaid(diagram.content) if diagram.content else ""
                    if _HAS_MERMAID and clean:
                        try:
                            st_mermaid(clean, height="280px")
                        except Exception:
                            st.info(et.topic.summary or diagram.caption)
                    else:
                        st.info(et.topic.summary or diagram.caption)
                st.markdown("")

            st.markdown(et.content_md)
            if et.key_takeaways:
                st.markdown("**Key takeaways:**")
                for kt in et.key_takeaways:
                    st.markdown(f"- {kt}")

            if et.inline_questions:
                st.markdown("---")
                st.markdown("**Check your understanding**")
                _render_inline_questions(et.topic.topic_id, et.inline_questions)

    if generating and progress:
        _pending_topics_fragment()

    st.markdown("---")
    quiz_ready = not generating or (progress and progress.get("bank") is not None)
    if st.button("📝 Take the Quiz", type="primary", disabled=not quiz_ready):
        if progress and progress.get("bank"):
            st.session_state["question_bank"] = progress["bank"]
        st.session_state["page"] = "quiz"
        st.rerun()
    if not quiz_ready:
        st.caption("Quiz available after all topics are generated")


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
    avg = progress.get("avg_seconds_per_topic", 0)
    last_topic_at = progress.get("last_topic_at")

    if state == "enriching":
        if done == 0:
            st.info("⏳ Generating first topic...")
        else:
            # Estimate time into the current topic
            if last_topic_at and avg > 0:
                time_on_current = int(time.monotonic() - last_topic_at)
                remaining = max(0, int(avg) - time_on_current)
                eta_text = f"~{remaining}s remaining" if remaining > 5 else "almost ready"
                st.info(
                    f"⏳ {done} topic{'s' if done != 1 else ''} ready · "
                    f"Generating **{current}** · {eta_text}"
                )
            else:
                st.info(f"⏳ {done} topic{'s' if done != 1 else ''} ready · Generating **{current}**...")
    elif state == "quiz":
        st.info("⏳ Generating quiz questions...")
    elif state == "saving":
        st.info("⏳ Saving module...")


def _render_inline_questions(topic_id: str, questions: list[Question]) -> None:
    for i, q in enumerate(questions):
        key = f"inline_{topic_id}_{i}"
        answered_key = f"{key}_answered"

        st.markdown(f"**Q{i + 1}: {q.question_text}**")

        if q.question_type == "single_choice":
            already_answered = st.session_state.get(answered_key, False)
            # After answering, lock the radio and restore the chosen index
            saved_idx = st.session_state.get(f"{answered_key}_idx")
            choice = st.radio(
                label="",
                options=q.options,
                index=saved_idx,
                key=key,
                label_visibility="collapsed",
                disabled=already_answered,
            )
            if choice is not None and not already_answered:
                selected_idx = q.options.index(choice)
                is_correct = selected_idx in q.correct_answers
                st.session_state[answered_key] = True
                st.session_state[f"{answered_key}_idx"] = selected_idx
                st.session_state[f"{answered_key}_correct"] = is_correct
                st.rerun()

            if already_answered:
                is_correct = st.session_state.get(f"{answered_key}_correct", False)
                if is_correct:
                    st.success(f"Correct! {q.explanation}")
                else:
                    correct_text = q.options[q.correct_answers[0]]
                    st.error(f"Not quite. The correct answer is: **{correct_text}**. {q.explanation}")
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
