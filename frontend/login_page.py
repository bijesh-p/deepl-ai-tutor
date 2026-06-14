from __future__ import annotations

import streamlit as st

from backend.analytics.db import db_path_for_user, get_db
from backend.analytics.persistence import load_user_profile, save_user


def render_login_page() -> None:
    """Clean login — username + greyed password only. Routes to upload on success."""
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

        with st.form("login_form", border=True):
            username = st.text_input(
                "Username",
                value=st.session_state.get("_last_username", ""),
                placeholder="e.g. alice",
                autocomplete="username",
            )
            st.text_input(
                "Password",
                type="password",
                placeholder="(no authentication required)",
                disabled=True,
                help="Authentication is not enabled — your username is only used to keep your learning history.",
            )
            submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)

        if submitted:
            name = username.strip()
            if not name:
                st.error("Please enter a username.")
                return

            st.session_state["_last_username"] = name

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
