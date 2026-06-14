"""AI Tutor — Streamlit entry point.

Run with: uv run streamlit run app.py
"""
from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()

import streamlit as st
from backend.observability import setup_tracing
setup_tracing()

st.set_page_config(
    page_title="AI Tutor",
    page_icon="📚",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Provider → available models (from env or sensible defaults)
# ---------------------------------------------------------------------------

def _models_for_provider(provider: str) -> list[str]:
    """Return the model list for a provider.

    Each provider can have a custom list set in .env:
        AI_TUTOR_ANTHROPIC_MODELS=claude-sonnet-4-6,claude-haiku-4-5-20251001
        AI_TUTOR_PORTKEY_MODELS=@vertexai-global/anthropic.claude-sonnet-4-6,...
        AI_TUTOR_OLLAMA_MODELS=llama3.2,qwen2.5,mistral
    Falls back to a built-in default list if the env var is not set.
    """
    import os
    key = f"AI_TUTOR_{provider.upper()}_MODELS"
    raw = os.environ.get(key, "")
    if raw.strip():
        return [m.strip() for m in raw.split(",") if m.strip()]

    defaults: dict[str, list[str]] = {
        "anthropic": [
            "claude-sonnet-4-6",
            "claude-opus-4-8",
            "claude-haiku-4-5-20251001",
        ],
        "portkey": [
            "@vertexai-global/anthropic.claude-sonnet-4-6",
            "@vertexai-global/anthropic.claude-opus-4-8",
            "@vertexai-global/anthropic.claude-haiku-4-5-20251001",
        ],
        "ollama": [
            "llama3.2",
            "qwen2.5",
            "mistral",
            "gemma3",
        ],
    }
    return defaults.get(provider, [])


def _get_ollama_running_models() -> list[str]:
    import json
    import os
    import urllib.request

    base_url = os.environ.get("AI_TUTOR_OLLAMA_BASE_URL", "http://localhost:11434/v1")
    api_url = base_url.rstrip("/").removesuffix("/v1") + "/api/tags"
    try:
        with urllib.request.urlopen(api_url, timeout=2) as resp:
            data = json.loads(resp.read().decode())
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def _render_sidebar() -> None:
    import os

    logged_in = bool(st.session_state.get("username"))

    with st.sidebar:
        # ── User badge ────────────────────────────────────────────────────────
        if logged_in:
            username = st.session_state["username"]
            st.markdown(f"**{username}**")
            if st.button("Sign out", key="_signout"):
                for k in list(st.session_state.keys()):
                    del st.session_state[k]
                st.session_state["page"] = "login"
                st.rerun()
            st.markdown("---")

        # ── LLM Provider + Model ──────────────────────────────────────────────
        st.markdown("### LLM")

        providers = ["anthropic", "portkey", "ollama"]
        current_provider = st.session_state.get(
            "llm_provider",
            os.environ.get("AI_TUTOR_LLM_PROVIDER", "anthropic"),
        )
        idx = providers.index(current_provider) if current_provider in providers else 0
        provider = st.selectbox("Provider", providers, index=idx, key="_llm_provider_select")

        # Build model list; for Ollama prefer what's actually running
        if provider == "ollama":
            running = _get_ollama_running_models()
            model_list = running if running else _models_for_provider("ollama")
        else:
            model_list = _models_for_provider(provider)

        # Pick default: keep current if it's in the list, else first
        env_default = os.environ.get("AI_TUTOR_LLM_MODEL", "")
        current_model = st.session_state.get("llm_model", env_default)
        if st.session_state.get("llm_provider") != provider:
            # Provider changed — reset to first in list
            current_model = model_list[0] if model_list else ""
        model_idx = model_list.index(current_model) if current_model in model_list else 0

        if model_list:
            model = st.selectbox("Model", model_list, index=model_idx, key="_llm_model_select")
        else:
            model = st.text_input("Model", value=current_model, key="_llm_model_input",
                                  placeholder="e.g. llama3.2")

        st.session_state["llm_provider"] = provider
        st.session_state["llm_model"] = model

        st.markdown("---")

        # ── Observability ─────────────────────────────────────────────────────
        if logged_in:
            st.markdown("### Observability")
            tracing_on = st.toggle(
                "Tracing (Phoenix)",
                value=st.session_state.get("tracing_enabled", True),
                help="Send OTEL spans to local Arize Phoenix at http://localhost:6006",
                key="_tracing_toggle",
            )
            evals_on = st.toggle(
                "Evals (DeepEval)",
                value=st.session_state.get("evals_enabled", False),
                help="Run quality metrics after each session using the active LLM as judge",
                key="_evals_toggle",
            )
            st.session_state["tracing_enabled"] = tracing_on
            st.session_state["evals_enabled"] = evals_on
            if tracing_on:
                st.caption("Traces → [localhost:6006](http://localhost:6006)")

            st.markdown("---")

            # ── Navigation ────────────────────────────────────────────────────
            if st.button("New Module"):
                st.session_state["page"] = "upload"
                st.rerun()
            if st.button("Module Library"):
                st.session_state["page"] = "module_library"
                st.rerun()
            if st.button("System Check"):
                st.session_state["page"] = "system_check"
                st.rerun()

    # Active model caption below sidebar (shown in main area header row)
    if logged_in:
        st.caption(f"LLM: **{provider}** / `{model}`")


def main() -> None:
    import time as _time

    if "page" not in st.session_state:
        st.session_state["page"] = "login"

    # ── Redirect unauthenticated users straight to login ─────────────────────
    if not st.session_state.get("username") and st.session_state["page"] != "login":
        st.session_state["page"] = "login"

    _render_sidebar()

    # ── Global pipeline progress banner ──────────────────────────────────────
    progress = st.session_state.get("pipeline_progress")
    if progress and progress["state"] not in ("completed", "failed", "aborted"):
        elapsed = int(_time.monotonic() - progress["started_at"])
        state = progress["state"]
        label = {
            "parsing": "Parsing PDF...",
            "enriching": f"Generating slides ({progress.get('topics_enriched', 0)} ready)...",
            "quiz": "Generating quiz...",
            "saving": "Saving module...",
        }.get(state, "Working...")
        st.info(f"{label} ({elapsed}s)")

    page = st.session_state["page"]

    if page == "login":
        from frontend.login_page import render_login_page
        render_login_page()

    elif page == "system_check":
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
        bank = st.session_state.get("question_bank") or st.session_state.get("bank")
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
        st.session_state["page"] = "login"
        st.rerun()


if __name__ == "__main__":
    main()
