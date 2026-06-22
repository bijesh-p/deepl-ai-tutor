from __future__ import annotations

import streamlit as st

from backend.analytics.auth import check_admin_password, is_admin_username
from backend.analytics.db import db_path_for_user, get_db
from backend.analytics.persistence import load_user_profile, save_user

_LOGIN_CSS = """
<style>
/* ── Login page — full-viewport centred canvas (dark theme) ─────────────── */

/* Sidebar and its collapse control are completely absent on the login page. */
[data-testid="stSidebar"],
section[data-testid="stSidebar"],
[data-testid="stSidebarCollapseButton"] {
    display: none !important;
    width: 0 !important;
    min-width: 0 !important;
    overflow: hidden !important;
    pointer-events: none !important;
}

/* Hide Streamlit chrome completely on the login page */
#MainMenu                         { display: none !important; }
[data-testid="stToolbar"]         { display: none !important; }
[data-testid="stDecoration"]      { display: none !important; }
[data-testid="stStatusWidget"]    { display: none !important; }
.stAppToolbar                     { display: none !important; }
[data-testid="stAppToolbar"]      { display: none !important; }
header[data-testid="stHeader"],
[data-testid="stHeader"],
.stHeader                         { display: none !important; }

/* Stretch the app to full viewport and center everything */
.stApp {
    background: radial-gradient(ellipse at 30% 20%, #1E1B4B 0%, #0F1117 60%) !important;
    min-height: 100vh !important;
}
.block-container {
    padding-top: 0 !important;
    padding-bottom: 0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    min-height: 100vh !important;
    max-width: 100% !important;
}

/* The card itself. */
.st-key-login_canvas {
    background: #1A1D29;
    border-radius: 20px;
    box-shadow: 0 8px 40px rgba(99,102,241,0.18), 0 2px 8px rgba(0,0,0,0.4);
    padding: 2.5rem 2rem 2rem;
    width: 100%;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    border: 1px solid #2D2F3D;
}

/* Tab styling inside the card */
.st-key-login_canvas .stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: #0F1117;
    border-radius: 10px;
    padding: 4px;
}
.st-key-login_canvas .stTabs [data-baseweb="tab"] {
    border-radius: 7px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    padding: 6px 16px !important;
    color: #94A3B8 !important;
    background: transparent !important;
    border: none !important;
}
.st-key-login_canvas .stTabs [aria-selected="true"] {
    background: #1A1D29 !important;
    color: #F1F5F9 !important;
    font-weight: 600 !important;
    box-shadow: 0 1px 4px rgba(99,102,241,0.25) !important;
}

/* Input fields */
.st-key-login_canvas input {
    border-radius: 8px !important;
    border: 1px solid #3D3F55 !important;
    background: #0F1117 !important;
    color: #F1F5F9 !important;
    font-family: 'Inter', sans-serif !important;
}
.st-key-login_canvas input:focus {
    border-color: #6366F1 !important;
    box-shadow: 0 0 0 3px rgba(99,102,241,0.2) !important;
}
.st-key-login_canvas input::placeholder {
    color: #64748B !important;
}

/* Labels above inputs */
.st-key-login_canvas label, .st-key-login_canvas p {
    color: #94A3B8 !important;
}

/* Sign-in button */
.st-key-login_canvas .stFormSubmitButton > button {
    background: linear-gradient(135deg, #4F46E5 0%, #2563EB 100%) !important;
    border: none !important;
    border-radius: 10px !important;
    color: white !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    padding: 0.55rem 1rem !important;
    font-family: 'Inter', sans-serif !important;
    box-shadow: 0 2px 8px rgba(79,70,229,0.4) !important;
    transition: all 0.15s ease !important;
}
.st-key-login_canvas .stFormSubmitButton > button:hover {
    background: linear-gradient(135deg, #4338CA 0%, #1D4ED8 100%) !important;
    box-shadow: 0 4px 14px rgba(79,70,229,0.5) !important;
    transform: translateY(-1px) !important;
}
</style>
"""


def _do_login(name: str, is_admin: bool) -> None:
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

    saved_provider = profile.get("llm_provider", "")
    saved_model = profile.get("llm_model", "")
    if saved_provider:
        st.session_state["llm_provider"] = saved_provider
    if saved_model:
        st.session_state["llm_model"] = saved_model
    st.session_state["dark_mode"] = profile.get("dark_mode", True)  # default dark if no saved preference

    st.session_state["page"] = "upload"
    st.rerun()


def render_login_page() -> None:
    st.markdown(_LOGIN_CSS, unsafe_allow_html=True)

    # Three-column layout: outer spacers squeeze the card to ~460 px
    _, col, _ = st.columns([1, 1.6, 1])
    with col:
        # ── Card canvas — a real container, so the title/tabs/forms below
        # actually nest inside it (see _LOGIN_CSS comment for why this
        # replaced a raw open/close <div> across separate markdown calls). ──
        with st.container(key="login_canvas"):
            # Brand header
            st.markdown(
                """
<div style="text-align:center;padding:0.5rem 0 1.5rem;
    font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <div style="font-size:1.9rem;font-weight:800;letter-spacing:-0.03em;
      background:linear-gradient(135deg,#A5B4FC 0%,#818CF8 50%,#60A5FA 100%);
      -webkit-background-clip:text;-webkit-text-fill-color:transparent;
      background-clip:text;line-height:1.1;">AI Tutor</div>
  <div style="margin-top:8px;font-size:14px;font-weight:600;color:#94A3B8;
      letter-spacing:-0.01em;line-height:1.5;">
    Transform documents into<br>
    <span style="color:#818CF8;font-weight:700;">interactive learning modules</span>
  </div>
</div>
""",
                unsafe_allow_html=True,
            )

            # ── Login tabs ────────────────────────────────────────────────────
            user_tab, admin_tab = st.tabs(["  User Login  ", "  Admin Login  "])

            with user_tab:
                with st.form("user_login_form", border=False):
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
                        "Sign in", type="primary", use_container_width=True,
                    )

            with admin_tab:
                with st.form("admin_login_form", border=False):
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
                        "Sign in as Admin", type="primary", use_container_width=True,
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
