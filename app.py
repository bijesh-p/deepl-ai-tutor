"""AI Tutor — Streamlit entry point.

Run with: uv run streamlit run app.py
"""
from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import streamlit as st

st.set_page_config(
    page_title="AI Tutor",
    page_icon="📚",
    layout="wide",
)


def main() -> None:
    if "page" not in st.session_state:
        st.session_state["page"] = "upload"

    page = st.session_state["page"]

    if page == "upload":
        from frontend.upload_page import render_upload_page
        render_upload_page()

    elif page == "module_library":
        if st.session_state.get("module") is None:
            for key in ("module", "bank", "quiz", "quiz_answers", "quiz_result", "quiz_difficulty"):
                st.session_state.pop(key, None)
        from frontend.module_library_page import render_module_library_page
        render_module_library_page()

    elif page == "learn":
        module = st.session_state.get("module")
        if module is None:
            st.session_state["page"] = "module_library"
            st.rerun()
        from frontend.module_viewer import render_module_viewer
        render_module_viewer(module)

    elif page == "quiz":
        bank = st.session_state.get("bank")
        if bank is None:
            st.session_state["page"] = "module_library"
            st.rerun()
        from frontend.quiz_page import render_quiz_page
        render_quiz_page(bank)

    elif page == "results":
        result = st.session_state.get("quiz_result")
        if result is None:
            st.session_state["page"] = "module_library"
            st.rerun()
        from frontend.results_page import render_results_page
        render_results_page(result)

    else:
        st.session_state["page"] = "upload"
        st.rerun()


if __name__ == "__main__":
    main()
