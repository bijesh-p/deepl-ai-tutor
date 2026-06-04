from __future__ import annotations

import os
import streamlit as st
from analytics.db import get_db
from analytics.persistence import save_user


def render_login_page() -> None:
    st.title("AI Tutor")
    st.subheader("Welcome — please enter your details to continue")

    admin_username = os.environ.get("AI_TUTOR_ADMIN_USERNAME", "admin")
    admin_password = os.environ.get("AI_TUTOR_ADMIN_PASSWORD", "")

    username = st.text_input("Username", placeholder="Enter your name")

    is_admin_attempt = username.strip() == admin_username
    password = ""
    if is_admin_attempt:
        password = st.text_input("Password (admin)", type="password")

    if st.button("Enter", disabled=not username.strip()):
        name = username.strip()

        if is_admin_attempt:
            if not admin_password:
                st.error("Admin password is not configured. Set AI_TUTOR_ADMIN_PASSWORD in .env")
                return
            if password != admin_password:
                st.error("Incorrect password.")
                return
            db = get_db()
            user_id = save_user(name, role="admin", db=db)
            st.session_state["user_id"] = user_id
            st.session_state["username"] = name
            st.session_state["role"] = "admin"
            st.session_state["page"] = "admin_upload"
        else:
            db = get_db()
            user_id = save_user(name, role="user", db=db)
            st.session_state["user_id"] = user_id
            st.session_state["username"] = name
            st.session_state["role"] = "user"
            st.session_state["page"] = "module_library"

        st.rerun()
