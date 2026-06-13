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


_DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-6",
    "portkey": "@vertexai-global/anthropic.claude-sonnet-4-6",
    "ollama": "llama3.2",
}


def _render_sidebar() -> None:
    """Sidebar: LLM selector, navigation, active model badge."""
    import os

    with st.sidebar:
        st.markdown("### LLM Provider")

        providers = ["anthropic", "portkey", "ollama"]
        current_provider = st.session_state.get(
            "llm_provider",
            os.environ.get("AI_TUTOR_LLM_PROVIDER", "anthropic"),
        )
        idx = providers.index(current_provider) if current_provider in providers else 0
        provider = st.selectbox(
            "Provider", providers, index=idx, key="_llm_provider_select",
        )

        default_model = _DEFAULT_MODELS.get(provider, "claude-sonnet-4-6")
        if provider == "ollama":
            default_model = _get_ollama_default() or default_model
        current_model = st.session_state.get("llm_model", default_model)
        if st.session_state.get("llm_provider") != provider:
            current_model = default_model
        model = st.text_input("Model", value=current_model, key="_llm_model_input")

        st.session_state["llm_provider"] = provider
        st.session_state["llm_model"] = model

        st.markdown("---")

        if st.button("New Module"):
            st.session_state["page"] = "upload"
            st.rerun()
        if st.button("Module Library"):
            st.session_state["page"] = "module_library"
            st.rerun()
        if st.button("System Check"):
            st.session_state["page"] = "system_check"
            st.rerun()

    st.caption(f"LLM: **{provider}** / `{model}`")


def _get_ollama_default() -> str | None:
    import json
    import os
    import urllib.request

    base_url = os.environ.get("AI_TUTOR_OLLAMA_BASE_URL", "http://localhost:11434/v1")
    api_url = base_url.rstrip("/").removesuffix("/v1") + "/api/tags"
    try:
        with urllib.request.urlopen(api_url, timeout=2) as resp:
            data = json.loads(resp.read().decode())
        models = [m["name"] for m in data.get("models", [])]
        return models[0] if models else None
    except Exception:
        return None


def main() -> None:
    if "page" not in st.session_state:
        st.session_state["page"] = "upload"

    _render_sidebar()

    page = st.session_state["page"]

    if page == "system_check":
        from frontend.system_check_page import render_system_check_page
        render_system_check_page()

    elif page == "upload":
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

    elif page == "tutor_room":
        from frontend.tutor_room import render_tutor_room
        render_tutor_room()

    else:
        st.session_state["page"] = "upload"
        st.rerun()


if __name__ == "__main__":
    main()
