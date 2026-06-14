"""Streamlit page for the LangGraph adaptive tutor with diagnostic quiz and slide presentation."""
from __future__ import annotations

from dataclasses import asdict

import streamlit as st

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
        _init_tutor_state(module)
    else:
        _refresh_content_map(module)
        _inject_enriched_topic()

    state = st.session_state["tutor_state"]
    phase = st.session_state["tutor_phase"]
    graph = st.session_state["tutor_graph"]

    # Progress + end session in sidebar-style column
    col_main, col_meta = st.columns([4, 1])
    with col_meta:
        mastered = state.get("mastered_concepts", [])
        total = len(mastered) + 1 + len(state.get("remaining_concepts", []))
        st.metric("Progress", f"{len(mastered)}/{total}")
        depth = state.get("presentation_depth", "—")
        st.caption(f"Level: **{depth}**")
        if st.button("End Session"):
            _cleanup_tutor()
            st.session_state["page"] = "module_library"
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
            remaining = state.get("remaining_concepts", [])
            next_concept = remaining[0] if remaining else ""
            content_map = st.session_state.get("tutor_content_map", {})
            _inject_enriched_topic()
            if next_concept and next_concept in content_map:
                _advance_to_next(state, graph, content_map)
                st.rerun()
            else:
                st.info(f"Waiting for **{next_concept}** to finish generating...")
                _render_chat_history(state.get("chat_history", []))
                if st.button("Check again"):
                    _refresh_content_map(module)
                    st.rerun()

        elif phase == "done":
            _render_chat_history(state.get("chat_history", []))
            mastered = state.get("mastered_concepts", [])
            st.success(f"Session complete! You mastered **{len(mastered)}** concept(s).")
            if st.button("Back to Module Library"):
                _cleanup_tutor()
                st.session_state["page"] = "module_library"
                st.rerun()


# ---------------------------------------------------------------------------
# Phase renderers
# ---------------------------------------------------------------------------

def _render_diagnostic(state: dict, graph) -> None:
    questions = state.get("diagnostic_questions")
    concept = state["current_concept"]

    if not questions:
        with st.spinner(f"Preparing diagnostic for **{concept}**..."):
            _run_node(graph, state, "generate_diagnostic")
        st.rerun()

    progress = st.session_state.get("pipeline_progress", {})
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

    st.subheader(concept)

    if top_concepts:
        st.info("**Key concepts:** " + " | ".join(f"`{c}`" for c in top_concepts))

    if mermaid_code:
        if _HAS_MERMAID:
            st_mermaid(mermaid_code)
        else:
            st.code(mermaid_code, language="text")

    if audio_path:
        st.audio(audio_path, format="audio/mp3")

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

    if st.button("Ask me a question about this", type="primary"):
        _run_node(graph, state, "ask_question")
        st.session_state["tutor_phase"] = "answer"
        st.rerun()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _init_tutor_state(module) -> None:
    from backend.interactive_tutor.graph import GraphState

    topics = module.topics
    concepts = [t.topic.title for t in topics]
    summary_map = {t.topic.title: t.topic.summary for t in topics}
    content_map = {t.topic.title: t.content_md for t in topics}

    st.session_state["tutor_state"] = {
        "current_concept": concepts[0] if concepts else "",
        "concept_content": content_map.get(concepts[0], "") if concepts else "",
        "concept_summary": summary_map.get(concepts[0], "") if concepts else "",
        "current_question": None,
        "student_answer": "",
        "attempts": 0,
        "concept_mastered": False,
        "mastered_concepts": [],
        "remaining_concepts": concepts[1:] if len(concepts) > 1 else [],
        "chat_history": [],
        "user_id": st.session_state.get("user_id", ""),
        "module_id": module.module_id,
        "feedback": "",
        "diagnostic_questions": [],
        "diagnostic_answers": [],
        "diagnostic_score": 0.0,
        "presentation_depth": "intermediate",
        "topic_diagram": "",
        "topic_audio_path": "",
        "topic_top_concepts": [],
        "enriched_topic": None,
    }
    st.session_state["tutor_content_map"] = content_map
    st.session_state["tutor_summary_map"] = summary_map
    st.session_state["tutor_phase"] = "diagnostic"
    st.session_state["tutor_graph"] = build_tutor_graph()


def _inject_enriched_topic() -> None:
    """Copy the matching EnrichedTopic from pipeline progress into tutor state."""
    state = st.session_state.get("tutor_state")
    if not state:
        return
    progress = st.session_state.get("pipeline_progress", {})
    enriched_list = progress.get("enriched_topics", [])
    current = state.get("current_concept", "")
    for et in enriched_list:
        if et.topic.title == current:
            state["enriched_topic"] = asdict(et)
            # Also update content + summary from enriched
            state["concept_content"] = et.content_md
            return


def _advance_to_next(state: dict, graph, content_map: dict) -> None:
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


def _refresh_content_map(module) -> None:
    content_map = st.session_state.get("tutor_content_map", {})
    summary_map = st.session_state.get("tutor_summary_map", {})
    state = st.session_state.get("tutor_state")
    for t in module.topics:
        content_map[t.topic.title] = t.content_md
        summary_map[t.topic.title] = t.topic.summary
        if state and t.topic.title not in state.get("remaining_concepts", []):
            current = state.get("current_concept", "")
            mastered = state.get("mastered_concepts", [])
            remaining = state.get("remaining_concepts", [])
            if t.topic.title != current and t.topic.title not in mastered and t.topic.title not in remaining:
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


def _cleanup_tutor() -> None:
    for key in ("tutor_state", "tutor_phase", "tutor_graph", "tutor_content_map", "tutor_summary_map"):
        st.session_state.pop(key, None)
