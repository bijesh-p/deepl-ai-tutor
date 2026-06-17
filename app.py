"""AI Tutor — Streamlit entry point.

Run with: uv run streamlit run app.py
"""
from __future__ import annotations

from dotenv import load_dotenv
load_dotenv(override=True)  # override=True ensures .env always wins over OS-level env vars

import streamlit as st
from backend.observability import setup_tracing
setup_tracing()

st.set_page_config(
    page_title="AI Tutor",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from frontend.styles import inject_global_css
inject_global_css()

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
        # ── App name ──────────────────────────────────────────────────────────
        st.markdown(
            "<div style='font-size:15px;font-weight:700;color:#1E1B4B;"
            "letter-spacing:-0.02em;padding-bottom:8px;"
            "font-family:Inter,-apple-system,sans-serif;'>📚 AI Tutor</div>",
            unsafe_allow_html=True,
        )

        # ── User badge + sign-out ─────────────────────────────────────────────
        if logged_in:
            username = st.session_state["username"]
            role_label = "Admin" if st.session_state.get("is_admin") else "Student"
            st.markdown(
                f"<div style='font-family:Inter,sans-serif;padding:4px 2px 6px;line-height:1.35;'>"
                f"<div style='font-size:15px;font-weight:700;color:#1E1B4B;letter-spacing:-0.01em;'>{username}</div>"
                f"<div style='font-size:10px;font-weight:500;color:#818CF8;letter-spacing:0.05em;"
                f"text-transform:uppercase;'>{role_label}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            st.markdown("<span class='sb-signout-marker'></span>", unsafe_allow_html=True)
            if st.button("Sign out", key="_signout", use_container_width=True, help="Sign out of AI Tutor"):
                for k in list(st.session_state.keys()):
                    del st.session_state[k]
                st.session_state["page"] = "login"
                st.rerun()

        # ── Model ─────────────────────────────────────────────────────────────
        st.markdown("<div class='sb-label'>Model</div>", unsafe_allow_html=True)

        providers = ["anthropic", "portkey", "ollama"]
        current_provider = st.session_state.get(
            "llm_provider",
            os.environ.get("AI_TUTOR_LLM_PROVIDER", "anthropic"),
        )
        idx = providers.index(current_provider) if current_provider in providers else 0
        provider = st.selectbox("Provider", providers, index=idx, key="_llm_provider_select",
                                label_visibility="collapsed")

        if provider == "ollama":
            running = _get_ollama_running_models()
            model_list = running if running else _models_for_provider("ollama")
        else:
            model_list = _models_for_provider(provider)

        env_default = os.environ.get("AI_TUTOR_LLM_MODEL", "")
        current_model = st.session_state.get("llm_model", env_default)
        if st.session_state.get("llm_provider") != provider:
            current_model = model_list[0] if model_list else ""
        model_idx = model_list.index(current_model) if current_model in model_list else 0

        if model_list:
            model = st.selectbox("Model", model_list, index=model_idx, key="_llm_model_select",
                                 label_visibility="collapsed")
        else:
            model = st.text_input("Model", value=current_model, key="_llm_model_input",
                                  placeholder="e.g. llama3.2", label_visibility="collapsed")

        st.session_state["llm_provider"] = provider
        st.session_state["llm_model"] = model

        # ── Settings (audio + observability toggles) ──────────────────────────
        if logged_in:
            st.markdown("<div class='sb-label'>Settings</div>", unsafe_allow_html=True)

            audio_on = st.toggle(
                "Audio",
                value=st.session_state.get("audio_enabled", True),
                help="Enable TTS narration for slides and diagnostics",
                key="_audio_toggle",
            )
            tracing_on = st.toggle(
                "Tracing",
                value=st.session_state.get("tracing_enabled", True),
                help="Send OTEL spans to Arize Phoenix at localhost:6006",
                key="_tracing_toggle",
            )
            evals_on = st.toggle(
                "Evals",
                value=st.session_state.get("evals_enabled", False),
                help="Run DeepEval quality metrics using the active LLM as judge",
                key="_evals_toggle",
            )
            st.session_state["audio_enabled"] = audio_on
            st.session_state["tracing_enabled"] = tracing_on
            st.session_state["evals_enabled"] = evals_on

            # ── Navigation ────────────────────────────────────────────────────
            st.markdown("<div class='sb-label'>Navigate</div>", unsafe_allow_html=True)
            if st.button("+ New Module", use_container_width=True):
                st.session_state["page"] = "upload"
                st.rerun()
            if st.button("📚 Library", use_container_width=True):
                st.session_state["page"] = "module_library"
                st.rerun()
            if st.button("🩺 System Check", use_container_width=True):
                st.session_state["page"] = "system_check"
                st.rerun()
            if st.button("📊 Observability", use_container_width=True):
                st.session_state["page"] = "observability"
                st.rerun()

    # Active provider/model shown as a small caption in the main area
    if logged_in:
        st.caption(f"`{provider}` / `{model}`")


def main() -> None:
    import time as _time

    if "page" not in st.session_state:
        st.session_state["page"] = "login"

    # ── Redirect unauthenticated users straight to login ─────────────────────
    if not st.session_state.get("username") and st.session_state["page"] != "login":
        st.session_state["page"] = "login"

    if st.session_state["page"] != "login":
        _render_sidebar()

    # ── Global pipeline progress banner (non-upload pages only) ──────────────
    progress = st.session_state.get("pipeline_progress")
    _current_page = st.session_state.get("page", "")
    if (progress
            and progress["state"] not in ("completed", "failed", "aborted")
            and _current_page != "upload"):
        elapsed = int(_time.monotonic() - progress["started_at"])
        state = progress["state"]
        done = progress.get("topics_enriched", 0)
        icons = {"parsing": "🔍", "enriching": "✨", "quiz": "❓", "saving": "💾"}
        label = {
            "parsing": "Parsing document",
            "enriching": f"{done} slide(s) ready — generating more",
            "quiz": "Generating quiz questions",
            "saving": "Saving module",
        }.get(state, "Working")
        elapsed_txt = f" · {elapsed}s" if elapsed > 0 else ""
        st.info(f"{icons.get(state, '⏳')} {label}{elapsed_txt}")

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

    elif page == "mastery_report":
        module = st.session_state.get("module")
        if module is None:
            st.session_state["page"] = "module_library"
            st.rerun()
        from frontend.mastery_report_page import render_mastery_report_page
        render_mastery_report_page(module)

    elif page == "observability":
        from frontend.observability_page import render_observability_page
        render_observability_page()

    else:
        st.session_state["page"] = "login"
        st.rerun()


if __name__ == "__main__":
    main()
