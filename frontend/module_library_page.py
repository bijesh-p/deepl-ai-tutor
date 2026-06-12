from __future__ import annotations

import json

import streamlit as st

from backend.analytics.db import get_db
from backend.analytics.persistence import list_modules, delete_module, load_module
from backend.content.models import LearningModule
from backend.quiz.models import QuestionBank, QuizQuestion


def render_module_library_page() -> None:
    st.title("Module Library")
    st.caption(f"Welcome, **{st.session_state.get('username', '')}**")

    col1, col2 = st.columns([6, 1])
    with col2:
        if st.button("+ New Module"):
            st.session_state["page"] = "upload"
            st.rerun()

    db = get_db()
    modules = list_modules(db=db)

    if not modules:
        st.info("No learning modules available yet. Upload a PDF to generate one.")
        return

    st.markdown(f"**{len(modules)} module(s) available**")
    st.markdown("---")

    for mod in modules:
        col_title, col_date, col_actions = st.columns([4, 2, 2])

        with col_title:
            st.markdown(f"**{mod['title']}**")
            st.caption(f"Source: {mod['source_filename']}")

        with col_date:
            created = mod["created_at"][:10]
            st.markdown(f"Created: {created}")

        with col_actions:
            if st.button("Learn", key=f"learn_{mod['module_id']}", type="primary"):
                _load_and_navigate(mod["module_id"], db)
            if st.button("Delete", key=f"del_{mod['module_id']}", type="secondary"):
                delete_module(mod["module_id"], db=db)
                st.rerun()

        st.markdown("---")


def _load_and_navigate(module_id: str, db) -> None:
    row = load_module(module_id, db=db)
    if not row:
        st.error("Module not found in database.")
        return

    if not row.get("module_json"):
        st.warning(
            "This module was saved before the v0.3 update and its content cannot be loaded. "
            "Please delete it and regenerate it from the original PDF."
        )
        return

    module = LearningModule.from_json(row["module_json"])
    bank = _bank_from_json(row["question_bank_json"])

    st.session_state["module"] = module
    st.session_state["bank"] = bank
    st.session_state["page"] = "learn"
    st.rerun()


def _bank_from_json(raw: str) -> QuestionBank:
    data = json.loads(raw)
    questions = [
        QuizQuestion(
            question_id=q["question_id"],
            question_text=q["question_text"],
            question_type=q["question_type"],
            options=q["options"],
            correct_answers=q["correct_answers"],
            explanation=q["explanation"],
            difficulty=q["difficulty"],
            topic_id=q["topic_id"],
        )
        for q in data["questions"]
    ]
    return QuestionBank(module_id=data["module_id"], questions=questions)
