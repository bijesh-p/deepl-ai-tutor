"""Streamlit page for the LangGraph interactive tutor."""
from __future__ import annotations

import json

import streamlit as st

from backend.interactive_tutor import build_tutor_graph, GraphState


def render_tutor_room() -> None:
    st.title("AI Tutor Room")
    module = st.session_state.get("module")
    if module is None:
        st.warning("No module selected. Go to Module Library first.")
        if st.button("Go to Module Library"):
            st.session_state["page"] = "module_library"
            st.rerun()
        return

    st.caption(f"Module: **{module.title}**")

    if "tutor_state" not in st.session_state:
        concepts = [t.topic.title for t in module.topics]
        content_map = {t.topic.title: t.content_md for t in module.topics}

        st.session_state["tutor_state"] = {
            "current_concept": concepts[0] if concepts else "",
            "concept_content": content_map.get(concepts[0], "") if concepts else "",
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
        }
        st.session_state["tutor_content_map"] = content_map
        st.session_state["tutor_phase"] = "present"
        st.session_state["tutor_graph"] = build_tutor_graph()

    state = st.session_state["tutor_state"]
    phase = st.session_state["tutor_phase"]
    graph = st.session_state["tutor_graph"]

    col1, col2 = st.columns([3, 1])
    with col2:
        mastered = state.get("mastered_concepts", [])
        total = len(mastered) + 1 + len(state.get("remaining_concepts", []))
        st.metric("Progress", f"{len(mastered)}/{total} concepts")

        if st.button("End Session"):
            _cleanup_tutor()
            st.session_state["page"] = "module_library"
            st.rerun()

    with col1:
        _render_chat_history(state.get("chat_history", []))

    if phase == "present":
        if st.button("Start Learning", type="primary"):
            _run_node(graph, state, "present_concept")
            st.session_state["tutor_phase"] = "question"
            st.rerun()

    elif phase == "question":
        if st.button("Ask me a question", type="primary"):
            _run_node(graph, state, "ask_question")
            st.session_state["tutor_phase"] = "answer"
            st.rerun()

    elif phase == "answer":
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
                        _run_node(graph, state, "advance_concept")
                        content_map = st.session_state.get("tutor_content_map", {})
                        state["concept_content"] = content_map.get(state["current_concept"], "")
                        st.session_state["tutor_phase"] = "present"
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

    elif phase == "done":
        st.success("Session complete! Great job!")
        mastered = state.get("mastered_concepts", [])
        st.write(f"You mastered **{len(mastered)}** concept(s): {', '.join(mastered)}")
        if st.button("Back to Module Library"):
            _cleanup_tutor()
            st.session_state["page"] = "module_library"
            st.rerun()


def _run_node(graph, state: dict, node_name: str) -> None:
    """Run a single node function and merge result into state."""
    from backend.interactive_tutor.graph import (
        present_concept,
        ask_question,
        evaluate_response,
        provide_hint,
        simplify_foundations,
        _advance_concept,
        _session_complete,
    )

    node_map = {
        "present_concept": present_concept,
        "ask_question": ask_question,
        "evaluate_response": evaluate_response,
        "provide_hint": provide_hint,
        "simplify_foundations": simplify_foundations,
        "advance_concept": _advance_concept,
        "session_complete": _session_complete,
    }

    fn = node_map[node_name]
    updates = fn(state)
    state.update(updates)


def _render_chat_history(history: list[dict]) -> None:
    """Display chat messages."""
    for msg in history:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "tutor":
            st.chat_message("assistant").markdown(content)
        elif role == "student":
            st.chat_message("user").markdown(content)


def _cleanup_tutor() -> None:
    """Remove tutor state from session."""
    for key in ("tutor_state", "tutor_phase", "tutor_graph", "tutor_content_map"):
        st.session_state.pop(key, None)
