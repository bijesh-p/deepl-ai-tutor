"""Streamlit page for the LangGraph adaptive tutor with diagnostic quiz and slide presentation."""
from __future__ import annotations

import os
import time
from dataclasses import asdict

import streamlit as st

from backend.analytics.db import get_db
from backend.analytics.persistence import (
    delete_tutor_session,
    load_tutor_session,
    save_topic_mastery,
    save_tutor_session,
    save_user_profile,
)
from backend.interactive_tutor import build_tutor_graph
from frontend.audio_autostop import render_audio_autostop
from frontend.styles import concept_rail_html

try:
    from streamlit_mermaid import st_mermaid
    _HAS_MERMAID = True
except ImportError:
    _HAS_MERMAID = False


def render_tutor_room() -> None:
    render_audio_autostop()

    module = st.session_state.get("module")
    if module is None:
        st.title("AI Tutor")
        st.warning("No module selected. Go to Module Library first.")
        if st.button("Go to Module Library"):
            st.session_state["page"] = "module_library"
            st.rerun()
        return

    if st.button("← Back to Module Library", type="secondary", key="_back_tutor_room"):
        _end_session(st.session_state.get("tutor_state"))
        st.rerun()

    st.title("AI Tutor")
    st.caption(f"Module: **{module.title}**")

    if "tutor_state" not in st.session_state:
        _maybe_resume_session(module)
    else:
        _refresh_content_map(module)
        _inject_enriched_topic()

    state = st.session_state["tutor_state"]
    phase = st.session_state["tutor_phase"]
    graph = st.session_state["tutor_graph"]

    if st.session_state.get("tutor_error"):
        _render_tutor_error(module)
        return

    if st.session_state.get("_resumed_session") and phase != "done":
        col_info, col_restart = st.columns([4, 1])
        with col_info:
            st.info("Resuming your previous session on this module.")
        with col_restart:
            if st.button("Restart from scratch"):
                user_id = state.get("user_id", "") or st.session_state.get("user_id", "")
                db = get_db(st.session_state.get("db_path"))
                try:
                    delete_tutor_session(user_id, module.module_id, db=db)
                finally:
                    db.close()
                for key in ("tutor_state", "tutor_phase", "tutor_graph", "_resumed_session"):
                    st.session_state.pop(key, None)
                st.rerun()
        st.markdown("---")

    # ── Concept rail — "where am I" indicator across the whole module ────────
    st.markdown(
        concept_rail_html(
            mastered=state.get("mastered_concepts", []),
            current=state.get("current_concept", "") if phase != "done" else "",
            remaining=state.get("remaining_concepts", []),
        ),
        unsafe_allow_html=True,
    )

    # Progress + end session in sidebar-style column
    col_main, col_meta = st.columns([4, 1])
    with col_meta:
        mastered = state.get("mastered_concepts", [])
        remaining = state.get("remaining_concepts", [])
        total = len(mastered) + 1 + len(remaining)
        done = len(mastered)
        pct = done / total if total else 0
        st.caption(f"**Topics done: {done}/{total}**")
        st.progress(pct)

        current = state.get("current_concept", "")
        all_topics = mastered + ([current] if current else []) + remaining
        with st.expander("Topics", expanded=True):
            for t in all_topics:
                label = t[:30] + "…" if len(t) > 30 else t
                if t in mastered:
                    st.markdown(f"✅ {label}")
                elif t == current:
                    st.markdown(f"**▶ {label}**")
                else:
                    st.markdown(f"⬜ {label}")

        depth = state.get("presentation_depth", "—")
        st.caption(f"Level: **{depth}**")
        # Wait time tracking
        wait_total = st.session_state.get("total_wait_seconds", 0)
        if phase == "waiting":
            current_wait = int(time.monotonic() - st.session_state.get("waiting_since", time.monotonic()))
        else:
            current_wait = 0
        if wait_total + current_wait > 0:
            st.caption(f"Wait: {wait_total + current_wait}s")
        if st.button("End Session"):
            _end_session(state)
            st.rerun()

    with col_main:
        if phase == "diagnostic":
            _render_diagnostic(state, graph)

        elif phase == "slide":
            _render_slide(state, graph)

        elif phase == "question":
            current = state.get("current_concept", "")
            _render_chat_history(state.get("chat_history", []), concept=current)
            if st.session_state.get("tutor_visited_concepts"):
                if st.button("← Previous topic", type="secondary", key="prev_question"):
                    visited = st.session_state.get("tutor_visited_concepts", [])
                    if not visited:
                        st.rerun()
                    else:
                        prev = visited[-1]
                        content_map = st.session_state.get("tutor_content_map", {})
                        if prev not in content_map or not content_map[prev]:
                            st.warning("Content for previous topic is not available yet.")
                        else:
                            visited.pop()
                            state["remaining_concepts"].insert(0, state["current_concept"])
                            state["current_concept"] = prev
                            st.session_state["tutor_state"] = state
                            st.session_state["tutor_phase"] = "slide"
                            st.rerun()
            remaining = state.get("remaining_concepts", [])
            st.caption("The tutor will ask you a question to check your understanding of this topic.")
            col_ask, col_skip, col_lib = st.columns([2, 2, 2])
            with col_ask:
                if st.button("Ask me a question", type="primary"):
                    with st.spinner("Generating a question for you..."):
                        _run_node(graph, state, "ask_question")
                    st.session_state["tutor_phase"] = "answer"
                    st.rerun()
            with col_skip:
                if remaining:
                    if st.button("Next topic →", type="secondary"):
                        content_map = st.session_state.get("tutor_content_map", {})
                        _advance_to_next(state, graph, content_map)
                        st.rerun()
                else:
                    if st.button("Finish session ✓", type="secondary"):
                        _run_node(graph, state, "session_complete")
                        st.session_state["tutor_phase"] = "done"
                        st.rerun()
            with col_lib:
                if st.button("Back to Module Library"):
                    st.session_state["page"] = "module_library"
                    st.rerun()

        elif phase == "answer":
            current = state.get("current_concept", "")
            _render_chat_history(state.get("chat_history", []), concept=current)
            if st.session_state.get("tutor_visited_concepts"):
                if st.button("← Previous topic", type="secondary", key="prev_answer"):
                    visited = st.session_state.get("tutor_visited_concepts", [])
                    if not visited:
                        st.rerun()
                    else:
                        prev = visited[-1]
                        content_map = st.session_state.get("tutor_content_map", {})
                        if prev not in content_map or not content_map[prev]:
                            st.warning("Content for previous topic is not available yet.")
                        else:
                            visited.pop()
                            state["remaining_concepts"].insert(0, state["current_concept"])
                            state["current_concept"] = prev
                            st.session_state["tutor_state"] = state
                            st.session_state["tutor_phase"] = "slide"
                            st.rerun()
            question = state.get("current_question", {})
            if question:
                st.info("💬 Type your answer below. The tutor will give detailed feedback.")
                answer = st.text_area(
                    "Your answer:",
                    key="tutor_answer_input",
                    placeholder="Type your answer here…",
                )
                if st.button("Submit Answer", type="primary", disabled=not answer):
                    state["student_answer"] = answer
                    with st.spinner("Evaluating your answer..."):
                        _run_node(graph, state, "evaluate_response")

                    if state.get("concept_mastered", False):
                        _record_topic_mastery(state, state["current_concept"], mastered=True)
                        remaining = state.get("remaining_concepts", [])
                        if remaining:
                            next_concept = remaining[0]
                            content_map = st.session_state.get("tutor_content_map", {})
                            if next_concept not in content_map:
                                st.session_state["tutor_phase"] = "waiting"
                            else:
                                _advance_to_next(state, graph, content_map)
                        else:
                            _run_node(graph, state, "session_complete")
                            st.session_state["tutor_phase"] = "done"
                    elif state.get("attempts", 0) >= 3:
                        _run_node(graph, state, "simplify_foundations")
                        st.session_state["tutor_phase"] = "question"
                    else:
                        _run_node(graph, state, "provide_hint")
                        st.session_state["tutor_phase"] = "question"

                    st.rerun()

        elif phase == "waiting":
            # Start tracking how long the student has been waiting
            if "waiting_since" not in st.session_state:
                st.session_state["waiting_since"] = time.monotonic()

            remaining = state.get("remaining_concepts", [])
            next_concept = remaining[0] if remaining else ""
            content_map = st.session_state.get("tutor_content_map", {})
            _inject_enriched_topic()

            # Check if next topic is now enriched (non-stub)
            progress_info = st.session_state.get("pipeline_progress", {})
            enriched_list = progress_info.get("enriched_topics", [])
            next_enriched = next(
                (e for e in enriched_list if e.topic.title == next_concept and e.content_md),
                None,
            )

            if next_enriched:
                _advance_to_next(state, graph, content_map)
                st.session_state.pop("waiting_since", None)
                st.rerun()
            else:
                wait_elapsed = int(time.monotonic() - st.session_state["waiting_since"])
                topics_done = progress_info.get("topics_enriched", 0)
                topics_total = max(progress_info.get("total_topics", 0), topics_done)

                st.info(f"Preparing **{next_concept}**... ({wait_elapsed}s)")
                if topics_total > 0:
                    st.progress(
                        topics_done / topics_total,
                        text=f"Background: {topics_done}/{topics_total} slides ready",
                    )
                else:
                    st.caption(f"Slides ready so far: {topics_done}")

                _render_chat_history(state.get("chat_history", []))

                # After 10s of waiting, show a bridge review activity
                if wait_elapsed >= 10:
                    _render_bridge_activity(state)

                if st.button("Check again"):
                    _refresh_content_map(module)
                    st.rerun()

        elif phase == "done":
            mastered = state.get("mastered_concepts", [])
            depth = state.get("presentation_depth", "standard")

            st.markdown("## 🎓 Session Complete!")
            st.markdown(f"You've covered all **{len(mastered)}** topics in this module.")

            elapsed = int(time.monotonic() - st.session_state.get("tutor_started_at", time.monotonic()))
            mins, secs = elapsed // 60, elapsed % 60
            st.caption(f"⏱ Time spent: {mins}m {secs}s")

            st.markdown("---")
            st.markdown("**Topics covered:**")
            for topic in mastered:
                st.success(f"✅ {topic}")

            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("📊 View Mastery Report", use_container_width=True):
                    st.session_state["page"] = "mastery_report"
                    st.rerun()
            with col2:
                if st.button("📝 Take the Quiz", use_container_width=True):
                    st.session_state["page"] = "quiz"
                    st.rerun()
            with col3:
                if st.button("🏛 Back to Library", use_container_width=True):
                    _end_session(state)
                    st.rerun()

    _persist_session(state, st.session_state["tutor_phase"])


# ---------------------------------------------------------------------------
# Phase renderers
# ---------------------------------------------------------------------------

def _render_diagnostic(state: dict, graph) -> None:
    questions = state.get("diagnostic_questions")
    concept = state["current_concept"]

    progress = st.session_state.get("pipeline_progress", {})

    visited = st.session_state.get("tutor_visited_concepts", [])
    if not questions:
        # Only reuse prefetched questions for the very first concept
        prefetched = progress.get("diagnostic_questions", [])
        content_map = st.session_state.get("tutor_content_map", {})
        concept_content = content_map.get(concept, "")

        if prefetched and not visited:
            # First topic — use prefetched (already generated from doc start)
            state["diagnostic_questions"] = prefetched
            questions = prefetched
        else:
            # New topic — generate fresh questions from THIS topic's content
            state["concept_content"] = concept_content
            with st.spinner(f"Preparing questions for {concept}..."):
                _run_node(graph, state, "generate_diagnostic")
            st.rerun()

    # Play diagnostic audio — generated right after PDF parse, no wait
    diag_audio = progress.get("diagnostic_audio_path", "")
    if diag_audio and os.path.exists(diag_audio):
        st.audio(diag_audio, format="audio/mp3", autoplay=True)

    generating = progress.get("state") not in ("completed", "failed", "aborted", "")
    if generating:
        done = progress.get("topics_enriched", 0)
        total = max(progress.get("total_topics", 0), done)
        st.caption(f"Content generating in background... ({done}/{total} topics ready)")

    st.subheader(f"Before we begin: {concept}")
    st.info("Your answers help us set the right depth and pace for your session.")

    if st.session_state.get("tutor_visited_concepts"):
        if st.button("← Previous topic", type="secondary", key="diag_prev"):
            visited = st.session_state.get("tutor_visited_concepts", [])
            if not visited:
                st.rerun()
            else:
                prev = visited[-1]
                content_map = st.session_state.get("tutor_content_map", {})
                if prev not in content_map or not content_map[prev]:
                    st.warning("Content for previous topic is not available yet.")
                else:
                    visited.pop()
                    remaining = state.get("remaining_concepts", [])
                    state["remaining_concepts"] = [concept] + remaining
                    mastered = state.get("mastered_concepts", [])
                    if concept in mastered:
                        mastered.remove(concept)
                    state["mastered_concepts"] = mastered
                    state["current_concept"] = prev
                    state["attempts"] = 0
                    state["diagnostic_questions"] = []
                    st.session_state["tutor_visited_concepts"] = visited
                    st.session_state["tutor_state"] = state
                    st.session_state["tutor_phase"] = "slide"
                    st.rerun()

    answers = []
    for i, q in enumerate(questions):
        st.markdown(f"**Q{i+1}: {q['question_text']}**")
        choice = st.radio(
            label="",
            options=q["options"],
            index=None,
            key=f"diag_q_{i}",
            label_visibility="collapsed",
        )
        answers.append(q["options"].index(choice) if choice in q["options"] else 0)

    if st.button("Submit & Start Learning", type="primary"):
        state["diagnostic_answers"] = answers
        with st.spinner("Analysing your answers and preparing your personalised session..."):
            _run_node(graph, state, "evaluate_diagnostic")
            _inject_enriched_topic()
            _run_node(graph, state, "present_concept")
        st.session_state["tutor_phase"] = "slide"
        st.rerun()


_SLIDE_DURATION_DEFAULT_S = 60  # fallback when no audio duration available


def _clean_for_render(mermaid_code: str) -> str:
    import re
    cleaned = []
    for line in mermaid_code.strip().splitlines():
        if re.match(r'\s*click\s', line):
            continue
        if ':::' in line:
            line = re.sub(r':::[\w]+', '', line)
        cleaned.append(line)
    return "\n".join(cleaned)


def _render_slide(state: dict, graph) -> None:
    history = state.get("chat_history", [])
    slide = next((m for m in reversed(history) if m.get("role") == "slide"), None)

    if not slide:
        st.info("Preparing your lesson slide...")
        return

    concept = slide.get("concept", state["current_concept"])

    # Record this concept as visited (safety net for any path not through _advance_to_next)
    _visited = st.session_state.setdefault("tutor_visited_concepts", [])
    _cur = state.get("current_concept", "")
    if _cur and (not _visited or _visited[-1] != _cur):
        _visited.append(_cur)

    top_concepts = slide.get("top_concepts", [])
    transcript = slide.get("transcript", "")
    mermaid_code = slide.get("mermaid_code", "")
    diagram_caption = slide.get("diagram_caption", "")
    audio_path = slide.get("audio_path", "")
    # Use audio duration as the slide hold time so advance never interrupts playback
    slide_duration_s = _SLIDE_DURATION_DEFAULT_S

    st.subheader(concept)

    if top_concepts:
        st.info("**Key concepts:** " + " | ".join(f"`{c}`" for c in top_concepts))

    if mermaid_code and mermaid_code.strip():
        from backend.content.diagram_generator import _sanitize_mermaid
        clean_mermaid = _sanitize_mermaid(mermaid_code)
        if _HAS_MERMAID and clean_mermaid:
            render_code = _clean_for_render(clean_mermaid)
            st.markdown("<div style='max-width:100%;overflow:hidden;'>", unsafe_allow_html=True)
            try:
                st_mermaid(render_code, height="350px")
            except Exception:
                st.info(concept)
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info(concept)
        if diagram_caption:
            st.caption(f"↑ {diagram_caption}")

    if audio_path and os.path.exists(audio_path):
        st.audio(audio_path, format="audio/mp3", autoplay=True)

    with st.expander("Read transcript", expanded=not bool(audio_path)):
        st.markdown(transcript)

    depth = state.get("presentation_depth", "intermediate")
    score_pct = int(state.get("diagnostic_score", 0) * 100)
    st.caption(f"Adapted for: **{depth}** (diagnostic score: {score_pct}%)")

    # Show Q&A for current concept only
    qa_history = [
        m for m in history
        if m.get("role") != "slide" and m.get("concept", concept) == concept
    ]
    if qa_history:
        st.markdown("---")
        _render_chat_history(qa_history)

    # ── Slide timer: synced to audio length ───────────────────────────────────
    slide_key = f"slide_shown_at_{concept}"
    if slide_key not in st.session_state:
        st.session_state[slide_key] = time.monotonic()

    elapsed = int(time.monotonic() - st.session_state[slide_key])
    remaining_s = max(0, slide_duration_s - elapsed)

    remaining_concepts = state.get("remaining_concepts", [])
    has_next = bool(remaining_concepts)

    # Check if next concept is already generated or still being built
    next_concept = remaining_concepts[0] if remaining_concepts else ""
    content_map = st.session_state.get("tutor_content_map", {})
    next_ready = next_concept in content_map and bool(content_map[next_concept])

    col_q, col_next = st.columns([3, 1])
    with col_q:
        if st.button("Ask me a question about this", type="primary"):
            _run_node(graph, state, "ask_question")
            st.session_state["tutor_phase"] = "answer"
            st.rerun()
    # Previous topic button
    col_prev, col_next = st.columns(2)
    with col_prev:
        if st.session_state.get("tutor_visited_concepts"):
            if st.button("← Previous topic", type="secondary"):
                visited = st.session_state.get("tutor_visited_concepts", [])
                if not visited:
                    st.rerun()
                else:
                    prev_concept = visited[-1]
                    content_map = st.session_state.get("tutor_content_map", {})
                    if prev_concept not in content_map or not content_map[prev_concept]:
                        st.warning("Content for previous topic is not available yet.")
                    else:
                        visited.pop()
                        current = state.get("current_concept", "")
                        remaining = state.get("remaining_concepts", [])
                        state["remaining_concepts"] = [current] + remaining
                        state["current_concept"] = prev_concept
                        if prev_concept in state.get("mastered_concepts", []):
                            state["mastered_concepts"].remove(prev_concept)
                        state["chat_history"] = [
                            m for m in state.get("chat_history", [])
                            if m.get("concept", current) != current
                        ]
                        st.session_state["tutor_visited_concepts"] = visited
                        st.session_state["tutor_state"] = state
                        st.session_state["tutor_phase"] = "slide"
                        st.rerun()

    with col_next:
        if has_next:
            if next_ready:
                if st.button("Next slide →", type="secondary"):
                    visited = st.session_state.setdefault("tutor_visited_concepts", [])
                    current = state.get("current_concept", "")
                    if current and (not visited or visited[-1] != current):
                        visited.append(current)
                    _do_advance_from_slide(state, graph)
                    st.rerun()
            else:
                progress_info = st.session_state.get("pipeline_progress", {})
                avg = progress_info.get("avg_seconds_per_topic", 0)
                last_at = progress_info.get("last_topic_at")
                if avg > 0 and last_at:
                    waited = int(time.monotonic() - last_at)
                    eta = max(0, int(avg) - waited)
                    eta_txt = f"~{eta}s" if eta > 5 else "almost ready"
                else:
                    eta_txt = "generating..."
                st.button(f"Next slide ({eta_txt})", disabled=True, type="secondary")
        if not has_next:
            if st.button("Back to Module Library", type="secondary"):
                st.session_state["page"] = "module_library"
                st.rerun()


def _do_advance_from_slide(state: dict, graph) -> None:
    """Mark current concept mastered and move to next slide."""
    concept = state.get("current_concept", "")
    mastered = state.get("mastered_concepts", [])
    if concept and concept not in mastered:
        mastered.append(concept)
    state["mastered_concepts"] = mastered
    state["concept_mastered"] = True
    _record_topic_mastery(state, concept, mastered=True)

    remaining = state.get("remaining_concepts", [])
    content_map = st.session_state.get("tutor_content_map", {})

    if not remaining:
        _run_node(graph, state, "session_complete")
        st.session_state["tutor_phase"] = "done"
        return

    next_concept = remaining[0]
    # Clear the slide timer for the new slide
    slide_key = f"slide_shown_at_{next_concept}"
    st.session_state.pop(slide_key, None)

    if next_concept in content_map and content_map[next_concept]:
        _advance_to_next(state, graph, content_map)
    else:
        # Next slide not ready yet — go to waiting phase
        st.session_state["tutor_phase"] = "waiting"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _init_tutor_state(module) -> None:
    topics = module.topics
    concepts = list(dict.fromkeys(t.topic.title for t in topics))  # deduplicate preserving order
    summary_map = {t.topic.title: t.topic.summary for t in topics}
    content_map = {t.topic.title: t.content_md for t in topics}

    # Seed depth and mastery from persisted user profile
    profile = st.session_state.get("user_profile", {})
    prior_depth = profile.get("overall_depth", "intermediate")
    prior_mastery: dict = profile.get("topic_mastery", {})

    # Topics the user already mastered in any prior session go to front of mastered list
    already_mastered = [c for c in concepts if prior_mastery.get(c)]
    remaining = [c for c in concepts if c not in already_mastered]
    first_concept = remaining[0] if remaining else (concepts[0] if concepts else "")

    st.session_state["tutor_state"] = {
        "current_concept": first_concept,
        "concept_content": content_map.get(first_concept, ""),
        "concept_summary": summary_map.get(first_concept, ""),
        "current_question": None,
        "student_answer": "",
        "attempts": 0,
        "concept_mastered": False,
        "mastered_concepts": already_mastered,
        "remaining_concepts": remaining[1:] if len(remaining) > 1 else [],
        "chat_history": [],
        "user_id": st.session_state.get("user_id", ""),
        "module_id": module.module_id,
        "feedback": "",
        "diagnostic_questions": [],
        "diagnostic_answers": [],
        "diagnostic_score": 0.0,
        "presentation_depth": prior_depth,
        "topic_diagram": "",
        "topic_audio_path": "",
        "topic_top_concepts": [],
        "enriched_topic": None,
        "audio_enabled": st.session_state.get("audio_enabled", True),
    }
    st.session_state["tutor_content_map"] = content_map
    st.session_state["tutor_summary_map"] = summary_map
    st.session_state["tutor_phase"] = "diagnostic"
    st.session_state["tutor_graph"] = build_tutor_graph()
    if "tutor_started_at" not in st.session_state:
        st.session_state["tutor_started_at"] = time.monotonic()


def _maybe_resume_session(module) -> None:
    """Restore a saved tutor session for this user/module, or start fresh."""
    user_id = st.session_state.get("user_id", "")
    db = get_db(st.session_state.get("db_path"))
    try:
        saved = load_tutor_session(user_id, module.module_id, db=db) if user_id else None
    finally:
        db.close()

    if saved and saved["phase"] != "done":
        topics = module.topics
        st.session_state["tutor_content_map"] = {t.topic.title: t.content_md for t in topics}
        st.session_state["tutor_summary_map"] = {t.topic.title: t.topic.summary for t in topics}
        st.session_state["tutor_state"] = saved["state"]
        st.session_state["tutor_phase"] = saved["phase"]
        st.session_state["tutor_graph"] = build_tutor_graph()
        st.session_state["_resumed_session"] = True
        _refresh_content_map(module)
        _inject_enriched_topic()
    else:
        _init_tutor_state(module)


def _persist_session(state: dict, phase: str) -> None:
    """Save (or clear, once done) the tutor session for resume support."""
    user_id = state.get("user_id") or st.session_state.get("user_id", "")
    module_id = state.get("module_id")
    if not user_id or not module_id:
        return
    db = get_db(st.session_state.get("db_path"))
    try:
        if phase == "done":
            delete_tutor_session(user_id, module_id, db=db)
        else:
            save_tutor_session(user_id, module_id, state, phase, db=db)
    finally:
        db.close()


def _record_topic_mastery(state: dict, topic_id: str, mastered: bool) -> None:
    """Persist per-topic mastery status (mastered flag, depth, attempt count)."""
    user_id = state.get("user_id") or st.session_state.get("user_id", "")
    module_id = state.get("module_id")
    if not user_id or not module_id or not topic_id:
        return
    db = get_db(st.session_state.get("db_path"))
    try:
        save_topic_mastery(
            user_id, module_id, topic_id,
            mastered=mastered,
            difficulty=state.get("presentation_depth", "intermediate"),
            attempts=state.get("attempts", 0),
            db=db,
        )
    finally:
        db.close()


def _inject_enriched_topic() -> None:
    """Copy the matching EnrichedTopic from pipeline progress into tutor state.

    Skips stub topics (content_md == "") — stubs are placeholders created
    immediately after decompose so the tutor room can start without waiting
    for full enrichment.
    """
    state = st.session_state.get("tutor_state")
    if not state:
        return
    progress = st.session_state.get("pipeline_progress", {})
    enriched_list = progress.get("enriched_topics", [])
    current = state.get("current_concept", "")
    for et in enriched_list:
        if et.topic.title == current and et.content_md:  # skip stubs
            state["enriched_topic"] = asdict(et)
            state["concept_content"] = et.content_md
            return


def _advance_to_next(state: dict, graph, content_map: dict) -> None:
    # Push current concept before it changes
    visited = st.session_state.setdefault("tutor_visited_concepts", [])
    current = state.get("current_concept", "")
    if current and (not visited or visited[-1] != current):
        visited.append(current)

    # Accumulate wait time before clearing the timer
    if "waiting_since" in st.session_state:
        waited = int(time.monotonic() - st.session_state["waiting_since"])
        st.session_state["total_wait_seconds"] = (
            st.session_state.get("total_wait_seconds", 0) + waited
        )
        st.session_state.pop("waiting_since", None)

    _run_node(graph, state, "advance_concept")
    # Update content and summary for the new concept
    concept = state.get("current_concept", "")
    state["concept_content"] = content_map.get(concept, "")
    summary_map = st.session_state.get("tutor_summary_map", {})
    state["concept_summary"] = summary_map.get(concept, "")
    # Reset for fresh diagnostic on next topic
    state["diagnostic_questions"] = []
    state["enriched_topic"] = None
    _inject_enriched_topic()
    st.session_state["tutor_phase"] = "diagnostic"


def _render_bridge_activity(state: dict) -> None:
    """Show a review question from an already-enriched mastered topic while student waits."""
    mastered = state.get("mastered_concepts", [])
    progress = st.session_state.get("pipeline_progress", {})
    enriched_list = progress.get("enriched_topics", [])

    for et in enriched_list:
        if et.topic.title in mastered and et.inline_questions:
            q = et.inline_questions[0]
            st.markdown("---")
            st.markdown("**While you wait — review question from a topic you covered:**")
            st.markdown(f"*{q.question_text}*")
            for i, opt in enumerate(q.options):
                st.markdown(f"{i + 1}. {opt}")
            with st.expander("See answer"):
                correct_idx = q.correct_answers[0] if q.correct_answers else 0
                st.markdown(f"**{q.options[correct_idx]}**")
                if q.explanation:
                    st.markdown(q.explanation)
            return

    st.markdown("_Content is being prepared — it will appear shortly._")


def _refresh_content_map(module) -> None:
    content_map = st.session_state.get("tutor_content_map", {})
    summary_map = st.session_state.get("tutor_summary_map", {})
    state = st.session_state.get("tutor_state")

    # Build the authoritative list of enriched topics from two sources:
    # 1. module.topics — what was available at redirect time (just slide 1)
    # 2. pipeline_progress["enriched_topics"] — live list as background publishes more
    seen_titles: set[str] = set()
    all_enriched = list(module.topics)
    pipeline_progress = st.session_state.get("pipeline_progress", {})
    for et in pipeline_progress.get("enriched_topics", []):
        if et.topic.title not in seen_titles:
            all_enriched.append(et)
            seen_titles.add(et.topic.title)

    for t in all_enriched:
        if not t.content_md:
            continue  # skip stubs / not-yet-enriched placeholders
        content_map[t.topic.title] = t.content_md
        summary_map[t.topic.title] = t.topic.summary
        if state:
            current = state.get("current_concept", "")
            mastered = state.get("mastered_concepts", [])
            remaining = state.get("remaining_concepts", [])
            if (t.topic.title != current
                    and t.topic.title not in mastered
                    and t.topic.title not in remaining):
                remaining.append(t.topic.title)

    st.session_state["tutor_content_map"] = content_map
    st.session_state["tutor_summary_map"] = summary_map


def _render_tutor_error(module) -> None:
    err = st.session_state.get("tutor_error", {})
    node = err.get("node", "unknown")
    detail = err.get("detail", "")

    st.error(f"Something went wrong while the tutor was processing: **{node}**")
    if detail:
        with st.expander("Technical details"):
            st.code(detail, language=None)

    col_retry, col_reset = st.columns(2)
    with col_retry:
        if st.button("Try again", type="primary", key="_tutor_retry"):
            st.session_state.pop("tutor_error", None)
            st.rerun()
    with col_reset:
        if st.button("Reset session", type="secondary", key="_tutor_reset"):
            user_id = st.session_state.get("user_id", "")
            db = get_db(st.session_state.get("db_path"))
            try:
                delete_tutor_session(user_id, module.module_id, db=db)
            finally:
                db.close()
            for key in ("tutor_state", "tutor_phase", "tutor_graph", "tutor_content_map",
                        "tutor_summary_map", "_resumed_session", "tutor_error"):
                st.session_state.pop(key, None)
            st.rerun()


def _run_node(graph, state: dict, node_name: str) -> None:
    from backend.interactive_tutor.graph import (
        generate_diagnostic, evaluate_diagnostic,
        present_concept, ask_question, evaluate_response,
        provide_hint, simplify_foundations,
        _advance_concept, _session_complete,
    )
    node_map = {
        "generate_diagnostic": generate_diagnostic,
        "evaluate_diagnostic": evaluate_diagnostic,
        "present_concept": present_concept,
        "ask_question": ask_question,
        "evaluate_response": evaluate_response,
        "provide_hint": provide_hint,
        "simplify_foundations": simplify_foundations,
        "advance_concept": _advance_concept,
        "session_complete": _session_complete,
    }
    try:
        updates = node_map[node_name](state)
        state.update(updates)
    except Exception as exc:
        st.session_state["tutor_error"] = {"node": node_name, "detail": str(exc)}
        st.rerun()  # abort rest of button handler; next render shows error UI


def _render_chat_history(history: list[dict], concept: str = "") -> None:
    for msg in history:
        role = msg.get("role", "")
        if role == "slide":
            continue
        # If concept filter set, only show messages for that concept
        # (messages without a concept tag are legacy — show them always)
        if concept and msg.get("concept") and msg.get("concept") != concept:
            continue
        content = msg.get("content", "")
        if role == "tutor" and content:
            st.chat_message("assistant").markdown(content)
        elif role == "student" and content:
            st.chat_message("user").markdown(content)


def _end_session(state: dict | None = None) -> None:
    """Abort background pipeline, persist user profile, then clean up tutor state."""
    # 1. Abort pipeline if still running
    abort_event = st.session_state.get("pipeline_abort_event")
    if abort_event:
        abort_event.set()

    # 2. Persist user profile
    if state:
        user_id = state.get("user_id") or st.session_state.get("user_id", "")
        if user_id:
            mastered = state.get("mastered_concepts", [])
            # Include current concept if it was just mastered
            if state.get("concept_mastered") and state.get("current_concept"):
                mastered = list(mastered) + [state["current_concept"]]
            topic_mastery = {c: True for c in mastered}
            depth = state.get("presentation_depth", "intermediate")
            module_id = state.get("module_id")
            try:
                db = get_db(st.session_state.get("db_path"))
                save_user_profile(
                    user_id=user_id,
                    overall_depth=depth,
                    topic_mastery=topic_mastery,
                    module_id=module_id,
                    llm_provider=st.session_state.get("llm_provider", ""),
                    llm_model=st.session_state.get("llm_model", ""),
                    db=db,
                )
                db.close()
                # Update in-session profile so it's fresh if user starts again
                profile = st.session_state.get("user_profile", {})
                profile["overall_depth"] = depth
                profile["topic_mastery"] = {**profile.get("topic_mastery", {}), **topic_mastery}
                st.session_state["user_profile"] = profile
            except Exception:
                pass  # profile save is best-effort

            # Record an "in progress" mastery row if the session ended mid-concept
            if not state.get("concept_mastered") and state.get("current_concept"):
                _record_topic_mastery(state, state["current_concept"], mastered=False)

            # Clear any resumable session row now that the session has ended
            if module_id:
                db = get_db(st.session_state.get("db_path"))
                try:
                    delete_tutor_session(user_id, module_id, db=db)
                finally:
                    db.close()

    # 3. Run DeepEval quality metrics asynchronously (fire-and-forget)
    if state:
        _trigger_evals(state)

    # 4. Clean up tutor session state
    for key in (
        "tutor_state", "tutor_phase", "tutor_graph", "tutor_content_map",
        "tutor_summary_map", "tutor_visited_concepts", "tutor_started_at",
        "_resumed_session", "total_wait_seconds", "waiting_since",
    ):
        st.session_state.pop(key, None)

    st.session_state["page"] = "module_library"


def _trigger_evals(state: dict) -> None:
    """Start DeepEval quality checks in a background thread — only if enabled in sidebar."""
    if not st.session_state.get("evals_enabled", False):
        return
    try:
        from backend.observability.eval_runner import run_session_evals_async

        # Capture provider/model now (session_state not safe to read from daemon thread)
        provider = st.session_state.get("llm_provider")
        model = st.session_state.get("llm_model")

        # Collect source text from pipeline progress for faithfulness checks
        progress = st.session_state.get("pipeline_progress", {})
        enriched_list = progress.get("enriched_topics", [])
        source_text = "\n\n".join(et.content_md for et in enriched_list)

        run_session_evals_async(
            chat_history=state.get("chat_history", []),
            source_text=source_text,
            user_id=state.get("user_id", ""),
            module_id=state.get("module_id", ""),
            provider=provider,
            model=model,
            db_path=st.session_state.get("db_path"),
        )
    except Exception:
        pass  # evals are best-effort — never crash the UI
