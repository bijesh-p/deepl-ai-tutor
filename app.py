import streamlit as st

st.set_page_config(
    page_title="AI Tutor",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="auto",
)

# Initialise navigation state
if "page" not in st.session_state:
    st.session_state["page"] = "upload"

page = st.session_state["page"]

if page == "upload":
    from frontend.upload_page import render_upload_page
    render_upload_page()

elif page == "learn":
    module = st.session_state.get("module")
    if module is None:
        st.session_state["page"] = "upload"
        st.rerun()
    from frontend.module_viewer import render_module_viewer
    render_module_viewer(module)

elif page == "quiz":
    bank = st.session_state.get("bank")
    if bank is None:
        st.session_state["page"] = "upload"
        st.rerun()
    from frontend.quiz_page import render_quiz_page
    render_quiz_page(bank)

elif page == "results":
    result = st.session_state.get("quiz_result")
    stats = st.session_state.get("quiz_stats")
    if result is None or stats is None:
        st.session_state["page"] = "quiz"
        st.rerun()
    from frontend.results_page import render_results_page
    render_results_page(result, stats)
