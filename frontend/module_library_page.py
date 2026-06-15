from __future__ import annotations

import json

import streamlit as st

from backend.analytics.db import get_db, get_shared_db
from backend.analytics.persistence import (
    delete_module,
    get_published_modules,
    list_modules,
    load_module,
    load_published_module,
    publish_module,
    unpublish_module,
)
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

    db = get_db(st.session_state.get("db_path"))
    shared_db = get_shared_db()
    is_admin = bool(st.session_state.get("is_admin"))

    _render_my_modules(db, shared_db, is_admin)
    st.markdown("---")
    _render_shared_library(shared_db)


def _render_my_modules(db, shared_db, is_admin: bool) -> None:
    st.markdown("### My Modules")

    modules = list_modules(db=db)
    if not modules:
        st.info("No learning modules available yet. Upload a PDF to generate one.")
        return

    st.markdown(f"**{len(modules)} module(s) available**")
    st.markdown("---")

    for mod in modules:
        col_title, col_date, col_actions = st.columns([4, 2, 2])

        with col_title:
            title = mod["title"]
            if mod.get("is_published"):
                title += "  🌐 *Published*"
            st.markdown(f"**{title}**")
            st.caption(f"Source: {mod['source_filename']}")

        with col_date:
            created = mod["created_at"][:10]
            st.markdown(f"Created: {created}")

        with col_actions:
            if st.button("Learn", key=f"learn_{mod['module_id']}", type="primary"):
                _load_and_navigate(mod["module_id"], db)
            if st.button("Mastery Report", key=f"mastery_{mod['module_id']}", type="secondary"):
                _load_for_mastery_report(mod["module_id"], db)
            if st.button("Delete", key=f"del_{mod['module_id']}", type="secondary"):
                delete_module(mod["module_id"], db=db)
                st.rerun()
            if is_admin:
                if mod.get("is_published"):
                    if st.button("Unpublish", key=f"unpub_{mod['module_id']}"):
                        unpublish_module(mod["module_id"], db=db, shared_db=shared_db)
                        st.rerun()
                else:
                    if st.button("Publish", key=f"pub_{mod['module_id']}"):
                        publish_module(mod["module_id"], db=db, shared_db=shared_db)
                        st.rerun()

        st.markdown("---")


def _render_shared_library(shared_db) -> None:
    st.markdown("### Shared Library")
    st.caption("Modules published by admins — available to all users.")

    shared_modules = get_published_modules(shared_db)
    if not shared_modules:
        st.info("No published modules yet.")
        return

    st.markdown(f"**{len(shared_modules)} module(s) available**")
    st.markdown("---")

    for mod in shared_modules:
        col_title, col_date, col_actions = st.columns([4, 2, 2])

        with col_title:
            st.markdown(f"**{mod['title']}**")
            st.caption(f"Source: {mod['source_filename']} · Published by {mod['created_by']}")

        with col_date:
            published = mod["published_at"][:10]
            st.markdown(f"Published: {published}")

        with col_actions:
            if st.button("Learn", key=f"slearn_{mod['module_id']}", type="primary"):
                _load_published_and_navigate(mod["module_id"], shared_db)

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


def _load_for_mastery_report(module_id: str, db) -> None:
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

    st.session_state["module"] = module
    st.session_state["page"] = "mastery_report"
    st.rerun()


def _load_published_and_navigate(module_id: str, shared_db) -> None:
    row = load_published_module(module_id, shared_db=shared_db)
    if not row:
        st.error("Module not found in shared library.")
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
