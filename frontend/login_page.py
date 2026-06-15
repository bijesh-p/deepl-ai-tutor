from __future__ import annotations

import streamlit as st

from backend.analytics.auth import check_admin_password, is_admin_username
from backend.analytics.db import db_path_for_user, get_db
from backend.analytics.persistence import load_user_profile, save_user


def _do_login(name: str, is_admin: bool) -> None:
    """Shared post-auth logic: load/create user, populate session state, redirect."""
    st.session_state["_last_username"] = name
    st.session_state["is_admin"] = is_admin

    db_path = db_path_for_user(name)
    db = get_db(db_path)
    user_id = save_user(name, db=db)
    profile = load_user_profile(user_id, db=db)
    db.close()

    st.session_state["username"] = name
    st.session_state["user_id"] = user_id
    st.session_state["user_profile"] = profile
    st.session_state["db_path"] = db_path

    # Restore LLM preferences saved from previous session
    saved_provider = profile.get("llm_provider", "")
    saved_model = profile.get("llm_model", "")
    if saved_provider:
        st.session_state["llm_provider"] = saved_provider
    if saved_model:
        st.session_state["llm_model"] = saved_model

    st.session_state["page"] = "upload"
    st.rerun()


def render_login_page() -> None:
    """Two-mode login: User (no password) and Admin (password required)."""
    # Hide the sidebar entirely on the login screen
    st.markdown(
        "<style>[data-testid='stSidebar']{display:none}</style>",
        unsafe_allow_html=True,
    )

    # Centre the form with empty columns
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("## AI Tutor")
        st.markdown("##### Sign in to continue")
        st.markdown("")

        user_tab, admin_tab = st.tabs(["User Login", "Admin Login"])

        with user_tab:
            with st.form("user_login_form", border=True):
                user_username = st.text_input(
                    "Username",
                    value=st.session_state.get("_last_username", ""),
                    placeholder="e.g. alice",
                    autocomplete="username",
                    key="user_username",
                )
                st.text_input(
                    "Password",
                    type="password",
                    disabled=True,
                    placeholder="Not required for regular users",
                    key="user_password",
                )
                user_submitted = st.form_submit_button(
                    "Sign in", type="primary", use_container_width=True
                )

        with admin_tab:
            with st.form("admin_login_form", border=True):
                admin_username = st.text_input(
                    "Username",
                    placeholder="e.g. admin",
                    autocomplete="username",
                    key="admin_username",
                )
                admin_password = st.text_input(
                    "Password",
                    type="password",
                    placeholder="Admin password",
                    key="admin_password",
                )
                admin_submitted = st.form_submit_button(
                    "Sign in as admin", type="primary", use_container_width=True
                )

        if user_submitted:
            name = user_username.strip()
            if not name:
                st.error("Please enter a username.")
                return
            _do_login(name, is_admin=False)

        if admin_submitted:
            name = admin_username.strip()
            if not name:
                st.error("Please enter a username.")
                return
            if not is_admin_username(name):
                st.error("This username is not registered as an admin.")
                return
            if not check_admin_password(admin_password):
                st.error("Incorrect admin password.")
                return
            _do_login(name, is_admin=True)
