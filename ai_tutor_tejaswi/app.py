import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="AI Tutor", page_icon="📚", layout="wide")

for key, default in [
    ("page", "upload"),
    ("user_id", None),
    ("username", ""),
    ("module", None),
    ("question_bank", None),
    ("quiz_result", None),
    ("module_stats", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

page = st.session_state.page

if page == "upload":
    from frontend.upload_page import render_upload_page
    render_upload_page()
elif page == "learn":
    from frontend.module_viewer import render_module_viewer
    render_module_viewer(st.session_state.module)
elif page == "quiz":
    from frontend.quiz_page import render_quiz_page
    render_quiz_page(st.session_state.question_bank)
elif page == "results":
    from frontend.results_page import render_results_page
    render_results_page(st.session_state.quiz_result, st.session_state.module_stats)
else:
    st.error(f"Unknown page: {page}")
    if st.button("Go Home"):
        st.session_state.page = "upload"
        st.rerun()
