"""AI Tutor — Streamlit entry point.

Run with: uv run streamlit run app.py
"""
from __future__ import annotations

from dotenv import load_dotenv
load_dotenv(override=True)  # override=True ensures .env always wins over OS-level env vars

import streamlit as st
try:
    from backend.observability import setup_tracing
    setup_tracing()
except Exception:
    pass

from backend.core.mcp_client import warm_up_storage_server
warm_up_storage_server()

st.set_page_config(
    page_title="AI Tutor",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

from frontend.styles import inject_global_css
inject_global_css()
st.session_state.setdefault("dark_mode", True)

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
    header_text_color = "#F1F5F9" if st.session_state.get("dark_mode", True) else "#1E1B4B"

    with st.sidebar:
        # ── App name ──────────────────────────────────────────────────────────
        st.markdown(
            f"<div style='font-size:15px;font-weight:700;color:{header_text_color};"
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
                f"<div style='font-size:15px;font-weight:700;color:{header_text_color};letter-spacing:-0.01em;'>{username}</div>"
                f"<div style='font-size:10px;font-weight:500;color:#818CF8;letter-spacing:0.05em;"
                f"text-transform:uppercase;'>{role_label}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            st.markdown("<span class='sb-signout-marker'></span>", unsafe_allow_html=True)
            if st.button("Sign out", key="_signout", use_container_width=True, help="Sign out of AI Tutor"):
                for k in list(st.session_state.keys()):
                    del st.session_state[k]
                st.query_params.clear()
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

        # ── Settings (toggle buttons — same size as nav buttons) ─────────────
        if logged_in:
            st.markdown("<div class='sb-label'>Settings</div>", unsafe_allow_html=True)

            audio_on = st.session_state.get("audio_enabled", True)
            tracing_on = st.session_state.get("tracing_enabled", True)
            evals_on = st.session_state.get("evals_enabled", False)
            dark_on = st.session_state.get("dark_mode", True)

            if st.button(f"🔊 Audio {'· on' if audio_on else '· off'}", use_container_width=True, key="_audio_btn", help="Toggle TTS narration"):
                st.session_state["audio_enabled"] = not audio_on
                st.rerun()
            if st.button(f"📡 Tracing {'· on' if tracing_on else '· off'}", use_container_width=True, key="_tracing_btn", help="Toggle OTEL tracing"):
                st.session_state["tracing_enabled"] = not tracing_on
                st.rerun()
            if st.button(f"🧪 Evals {'· on' if evals_on else '· off'}", use_container_width=True, key="_evals_btn", help="Toggle DeepEval metrics"):
                st.session_state["evals_enabled"] = not evals_on
                st.rerun()
            if st.button(f"🌙 Dark mode {'· on' if dark_on else '· off'}", use_container_width=True, key="_dark_btn", help="Toggle dark theme"):
                new_dark = not dark_on
                st.session_state["dark_mode"] = new_dark
                try:
                    from backend.analytics.db import get_db
                    from backend.analytics.persistence import save_dark_mode
                    save_dark_mode(
                        st.session_state["user_id"],
                        new_dark,
                        db=get_db(st.session_state.get("db_path")),
                    )
                except Exception:
                    pass
                st.rerun()

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



def main() -> None:
    import time as _time

    if "page" not in st.session_state:
        st.session_state["page"] = "login"

    # ── Auto-restore session from query params after browser refresh ──────────
    if not st.session_state.get("username"):
        saved_user = st.query_params.get("user", "")
        if saved_user:
            from frontend.login_page import _do_login
            is_admin = st.query_params.get("admin", "0") == "1"
            _do_login(saved_user, is_admin)
            return

    # ── Redirect unauthenticated users straight to login ─────────────────────
    if not st.session_state.get("username") and st.session_state["page"] != "login":
        st.session_state["page"] = "login"

    if st.session_state["page"] != "login":
        _render_sidebar()
        from frontend.sidebar_toggle import render_sidebar_toggle
        render_sidebar_toggle()

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
            for key in ("module", "bank", "quiz", "quiz_answers", "quiz_result"):
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
