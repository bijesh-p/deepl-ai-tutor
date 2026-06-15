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

try:
    from streamlit_mermaid import st_mermaid
    _HAS_MERMAID = True
except ImportError:
    _HAS_MERMAID = False


def render_tutor_room() -> None:
    st.title("AI Tutor")
    module = st.session_state.get("module")
    if module is None:
        st.warning("No module selected. Go to Module Library first.")
        if st.button("Go to Module Library"):
            st.session_state["page"] = "module_library"
            st.rerun()
        return

    st.caption(f"Module: **{module.title}**")

    if "tutor_state" not in st.session_state:
        _maybe_resume_session(module)
    else:
        _refresh_content_map(module)
        _inject_enriched_topic()

    state = st.session_state["tutor_state"]
    phase = st.session_state["tutor_phase"]
    graph = st.session_state["tutor_graph"]

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

    # Progress + end session in sidebar-style column
    col_main, col_meta = st.columns([4, 1])
    with col_meta:
        mastered = state.get("mastered_concepts", [])
        total = len(mastered) + 1 + len(state.get("remaining_concepts", []))
        st.metric("Progress", f"{len(mastered)}/{total}")
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
            _render_chat_history(state.get("chat_history", []))
            if st.button("Ask me a question", type="primary"):
                _run_node(graph, state, "ask_question")
                st.session_state["tutor_phase"] = "answer"
                st.rerun()

        elif phase == "answer":
            _render_chat_history(state.get("chat_history", []))
            question = state.get("current_question", {})
            if question:
                answer = st.text_area(
                    "Your answer:",
                    key="tutor_answer_input",
                    placeholder="Type your answer here…",
                )
                if st.button("Submit Answer", type="primary", disabled=not answer):
                    state["student_answer"] = answer
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
                topics_total = progress_info.get("total_topics", 0)

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
            _render_chat_history(state.get("chat_history", []))
            mastered = state.get("mastered_concepts", [])
            st.success(f"Session complete! You mastered **{len(mastered)}** concept(s).")
            if st.button("Back to Module Library"):
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

    # Use prefetched questions from pipeline if available, else generate now
    if not questions:
        prefetched = progress.get("diagnostic_questions", [])
        if prefetched:
            state["diagnostic_questions"] = prefetched
            questions = prefetched
        else:
            with st.spinner(f"Preparing diagnostic for **{concept}**..."):
                _run_node(graph, state, "generate_diagnostic")
            st.rerun()

    # Play diagnostic audio — generated right after PDF parse, no wait
    diag_audio = progress.get("diagnostic_audio_path", "")
    if diag_audio and os.path.exists(diag_audio):
        st.audio(diag_audio, format="audio/mp3", autoplay=True)

    generating = progress.get("state") not in ("completed", "failed", "aborted", "")
    if generating:
        done = progress.get("topics_enriched", 0)
        total = progress.get("total_topics", 0)
        st.caption(f"Content generating in background... ({done}/{total} topics ready)")

    st.subheader(f"Before we begin: {concept}")
    st.markdown("Answer these questions to help us tailor the explanation to your level.")

    with st.form("diagnostic_form"):
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

        submitted = st.form_submit_button("Submit & Start Learning", type="primary")
        if submitted:
            state["diagnostic_answers"] = answers
            _run_node(graph, state, "evaluate_diagnostic")
            _inject_enriched_topic()
            _run_node(graph, state, "present_concept")
            st.session_state["tutor_phase"] = "slide"
            st.rerun()


_SLIDE_DURATION_DEFAULT_S = 60  # fallback when no audio duration available


def _render_slide(state: dict, graph) -> None:
    history = state.get("chat_history", [])
    slide = next((m for m in reversed(history) if m.get("role") == "slide"), None)

    if not slide:
        st.info("Preparing your lesson slide...")
        return

    concept = slide.get("concept", state["current_concept"])
    top_concepts = slide.get("top_concepts", [])
    transcript = slide.get("transcript", "")
    mermaid_code = slide.get("mermaid_code", "")
    audio_path = slide.get("audio_path", "")
    # Use audio duration as the slide hold time so advance never interrupts playback
    slide_duration_s = slide.get("audio_duration_s") or _SLIDE_DURATION_DEFAULT_S

    st.subheader(concept)

    if top_concepts:
        st.info("**Key concepts:** " + " | ".join(f"`{c}`" for c in top_concepts))

    if mermaid_code:
        if _HAS_MERMAID:
            st_mermaid(mermaid_code)
        else:
            st.code(mermaid_code, language="text")

    if audio_path and os.path.exists(audio_path):
        st.audio(audio_path, format="audio/mp3", autoplay=True)

    with st.expander("Read transcript", expanded=not bool(audio_path)):
        st.markdown(transcript)

    depth = state.get("presentation_depth", "intermediate")
    score_pct = int(state.get("diagnostic_score", 0) * 100)
    st.caption(f"Adapted for: **{depth}** (diagnostic score: {score_pct}%)")

    # Show previous Q&A (non-slide messages)
    qa_history = [m for m in history if m.get("role") != "slide"]
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

    col_q, col_next = st.columns([3, 1])
    with col_q:
        if st.button("Ask me a question about this", type="primary"):
            _run_node(graph, state, "ask_question")
            st.session_state["tutor_phase"] = "answer"
            st.rerun()
    with col_next:
        if has_next:
            lbl = f"Next slide ({remaining_s}s)" if remaining_s > 0 else "Next slide →"
            if st.button(lbl, type="secondary"):
                _do_advance_from_slide(state, graph)
                st.rerun()

    # Auto-advance when timer expires
    if has_next and remaining_s == 0:
        _do_advance_from_slide(state, graph)
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
    concepts = [t.topic.title for t in topics]
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
    updates = node_map[node_name](state)
    state.update(updates)


def _render_chat_history(history: list[dict]) -> None:
    for msg in history:
        role = msg.get("role", "")
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
    for key in ("tutor_state", "tutor_phase", "tutor_graph", "tutor_content_map", "tutor_summary_map"):
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
