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
    rename_module,
    unpublish_module,
)
from backend.content.models import LearningModule
from backend.quiz.models import QuestionBank, QuizQuestion
from frontend.styles import module_card_html


def render_module_library_page() -> None:
    username = st.session_state.get("username", "")

    # ── Page header ─────────────────────────────────────────────────────────
    col_title, col_obs, col_new = st.columns([5, 1.3, 1.2])
    with col_title:
        dark = st.session_state.get("dark_mode", True)
        sub_color = "#94A3B8" if dark else "#6B7280"
        st.markdown(
            f"<h1 style='margin-bottom:2px;'>📚 Module Library</h1>"
            f"<div style='font-size:14px;color:{sub_color};margin-bottom:1rem;'>Welcome back, <b>{username}</b></div>",
            unsafe_allow_html=True,
        )
    with col_obs:
        if st.button("📊 Observability", key="obs_nav_lib", use_container_width=True):
            st.session_state["page"] = "observability"
            st.rerun()
    with col_new:
        if st.button("+ New Module", type="primary", key="new_mod_btn", use_container_width=True):
            st.session_state["page"] = "upload"
            st.rerun()

    db = get_db(st.session_state.get("db_path"))
    shared_db = get_shared_db()
    is_admin = bool(st.session_state.get("is_admin"))

    _render_my_modules(db, shared_db, is_admin)
    st.markdown("---")
    _render_shared_library(shared_db)

    import time
    progress = st.session_state.get("pipeline_progress")
    if progress and progress.get("state") not in ("completed", "failed", "aborted", None):
        time.sleep(3)
        st.rerun()


def _render_my_modules(db, shared_db, is_admin: bool) -> None:
    modules = list_modules(db=db)
    dark = st.session_state.get("dark_mode", True)

    st.markdown("### My Modules")
    if not modules:
        if dark:
            empty_bg, empty_border, title_c, sub_c = "#1A1D29", "#334155", "#F1F5F9", "#64748B"
        else:
            empty_bg, empty_border, title_c, sub_c = "#F9FAFB", "#E5E7EB", "#374151", "#9CA3AF"
        st.markdown(
            f'<div style="padding:2rem;text-align:center;background:{empty_bg};border:2px dashed {empty_border};border-radius:14px;">'
            f'<div style="font-size:2rem;margin-bottom:8px;">📄</div>'
            f'<div style="font-weight:600;color:{title_c};margin-bottom:4px;">No modules yet</div>'
            f'<div style="font-size:13px;color:{sub_c};">Upload a PDF, PPTX, or DOCX to generate your first learning module.</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        return

    st.caption(f"{len(modules)} module(s) in your library")

    for mod in modules:
        created = mod["created_at"][:10]
        source = mod.get("source_filename", "—")
        is_pub = bool(mod.get("is_published"))

        st.markdown(
            module_card_html(mod["title"], f"Source: {source}", f"Created {created}", is_published=is_pub, dark=dark),
            unsafe_allow_html=True,
        )

        col_learn, col_mastery, col_delete, col_publish = st.columns([1, 1, 1, 1])
        with col_learn:
            if st.button("Learn", key=f"learn_{mod['module_id']}", type="primary", use_container_width=True):
                _load_and_navigate(mod["module_id"], db)
        with col_mastery:
            if st.button("Mastery", key=f"mastery_{mod['module_id']}", type="secondary", use_container_width=True):
                _load_for_mastery_report(mod["module_id"], db)
        with action_cols[2]:
            with st.popover("Rename", use_container_width=True):
                new_name = st.text_input(
                    "New name", value=mod["title"], key=f"rename_input_{mod['module_id']}"
                )
                if st.button("Save", key=f"rename_save_{mod['module_id']}", type="primary", use_container_width=True):
                    stripped = new_name.strip()
                    if stripped and stripped != mod["title"]:
                        rename_module(mod["module_id"], stripped, db=db)
                        st.rerun()
        with action_cols[3]:
            if st.button("Delete", key=f"del_{mod['module_id']}", type="secondary", use_container_width=True):
                delete_module(mod["module_id"], db=db)
                st.rerun()
        if is_admin:
            with action_cols[4]:
        with col_delete:
            if st.button("Delete", key=f"del_{mod['module_id']}", type="secondary", use_container_width=True):
                delete_module(mod["module_id"], db=db)
                st.rerun()
        with col_publish:
            if is_admin:
                if is_pub:
                    if st.button("Unpublish", key=f"unpub_{mod['module_id']}", use_container_width=True):
                        unpublish_module(mod["module_id"], db=db, shared_db=shared_db)
                        st.rerun()
                else:
                    if st.button("Publish", key=f"pub_{mod['module_id']}", use_container_width=True):
                        publish_module(mod["module_id"], db=db, shared_db=shared_db)
                        st.rerun()

        st.markdown("<div style='margin-bottom:8px;'></div>", unsafe_allow_html=True)


def _render_shared_library(shared_db) -> None:
    dark = st.session_state.get("dark_mode", True)
    st.markdown("### Shared Library")
    st.caption("Modules published by admins — available to all users.")

    shared_modules = get_published_modules(shared_db)
    if not shared_modules:
        if dark:
            empty_bg, empty_border, sub_c = "#1A1D29", "#334155", "#64748B"
        else:
            empty_bg, empty_border, sub_c = "#F9FAFB", "#E5E7EB", "#9CA3AF"
        st.markdown(
            f'<div style="padding:1.5rem;text-align:center;background:{empty_bg};border:2px dashed {empty_border};border-radius:14px;">'
            f'<div style="font-size:13px;color:{sub_c};">No published modules yet.</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        return

    st.caption(f"{len(shared_modules)} module(s) available")

    for mod in shared_modules:
        published = mod["published_at"][:10]
        source = mod.get("source_filename", "—")
        created_by = mod.get("created_by", "admin")

        st.markdown(
            module_card_html(
                mod["title"],
                f"Source: {source}  ·  Published by {created_by}",
                f"Published {published}",
                is_published=True,
                dark=dark,
            ),
            unsafe_allow_html=True,
        )

        col_learn, col_pad = st.columns([1, 4])
        with col_learn:
            if st.button("Learn", key=f"slearn_{mod['module_id']}", type="primary", use_container_width=True):
                _load_published_and_navigate(mod["module_id"], shared_db)

        st.markdown("<div style='margin-bottom:8px;'></div>", unsafe_allow_html=True)


def _load_and_navigate(module_id: str, db) -> None:
    row = load_module(module_id, db=db)
    if not row:
        st.error("Module not found in database.")
        return
    if not row.get("module_json"):
        st.warning(
            "This module was saved before the v0.3 update and cannot be loaded. "
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
            "This module was saved before the v0.3 update and cannot be loaded. "
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
