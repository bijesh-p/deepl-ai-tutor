from __future__ import annotations

import json
import os
import urllib.request
import urllib.error

import streamlit as st

from frontend.nav import render_back_button

_PACKAGES = [
    "anthropic",
    "openai",
    "langgraph",
    "chromadb",
    "mcp",
    "streamlit",
    "fitz",
]

_PACKAGE_LABELS = {
    "fitz": "pymupdf",
}

_ENV_VARS = {
    "anthropic": ["AI_TUTOR_LLM_API_KEY"],
    "portkey": ["PORTKEY_API_KEY"],
    "ollama": ["AI_TUTOR_OLLAMA_BASE_URL"],
}


def render_system_check_page() -> None:
    render_back_button("← Back to Module Library", "module_library", key="_back_system_check")
    st.title("System Health Check")

    provider = st.session_state.get(
        "llm_provider",
        os.environ.get("AI_TUTOR_LLM_PROVIDER", "anthropic"),
    )
    model = st.session_state.get(
        "llm_model",
        os.environ.get("AI_TUTOR_LLM_MODEL", ""),
    )

    # ── LLM Connectivity ─────────────────────────────────────────────────────
    st.header("LLM Connectivity")
    st.caption(f"Provider: **{provider}** | Model: `{model or '(env default)'}` — change in the sidebar")

    _show_env_status(provider)

    with st.spinner("Testing LLM connection…"):
        ok, detail = _run_llm_test(provider, model)

    if ok:
        st.success(f"Connected — {detail}")
    else:
        st.error(f"Connection failed — {detail}")

    if st.button("Re-test Connection", type="primary"):
        _run_llm_test.clear()
        st.rerun()

    st.markdown("---")

    # ── Component Checks ─────────────────────────────────────────────────────
    st.header("Component Checks")
    if st.button("Run All Checks"):
        _check_database()
        _check_ollama_server()
        _check_packages()


@st.cache_data(ttl=120, show_spinner=False)
def _run_llm_test(provider: str, model: str) -> tuple[bool, str]:
    """Run a lightweight API ping. Cached for 120 s; clear with .clear()."""
    import traceback
    from dotenv import load_dotenv
    load_dotenv(override=True)  # re-apply .env so OS-level stale vars don't win
    try:
        from backend.core.llm_client import LLMFactory
        client = LLMFactory.create(provider=provider, model=model or None)
        response = client.generate("Reply with the single word: OK")
        return True, f"model `{client.model}` → `{response}`"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}\n\n```\n{traceback.format_exc()}\n```"


def _mask(value: str) -> str:
    if len(value) <= 4:
        return "***"
    return value[:4] + "***"


def _show_env_status(provider: str) -> None:
    var_names = _ENV_VARS.get(provider, [])
    for var in var_names:
        value = os.environ.get(var, "")
        if value and value not in ("your-anthropic-api-key-here", "your-portkey-api-key-here"):
            st.info(f"`{var}` = `{_mask(value)}`")
        else:
            st.warning(f"`{var}` is **not set** — add it to `.env` and restart the app")


def _check_database() -> None:
    try:
        from backend.analytics.db import get_db

        db_path = st.session_state.get("db_path") or os.environ.get("AI_TUTOR_DB_PATH", "data/ai_tutor.db")
        conn = get_db(db_path)
        conn.execute("SELECT 1")
        st.success(f"Database — OK (`{db_path}`)")
    except Exception as e:
        st.error(f"Database — FAILED: {e}")


def _check_ollama_server() -> None:
    base_url = os.environ.get("AI_TUTOR_OLLAMA_BASE_URL", "http://localhost:11434/v1")
    api_url = base_url.rstrip("/").removesuffix("/v1") + "/api/tags"
    try:
        with urllib.request.urlopen(api_url, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        models = [m["name"] for m in data.get("models", [])]
        if models:
            st.success(f"Ollama server — OK, models: {', '.join(models)}")
        else:
            st.warning("Ollama server — reachable but no models pulled. Run `ollama pull <model>`.")
    except urllib.error.URLError as e:
        st.error(f"Ollama server — not reachable at `{api_url}`: {e.reason}")
    except Exception as e:
        st.error(f"Ollama server — error: {e}")


def _check_packages() -> None:
    import importlib

    all_ok = True
    results = []
    for pkg in _PACKAGES:
        label = _PACKAGE_LABELS.get(pkg, pkg)
        try:
            mod = importlib.import_module(pkg)
            version = getattr(mod, "__version__", "installed")
            results.append((label, True, version))
        except ImportError:
            results.append((label, False, "not installed"))
            all_ok = False

    if all_ok:
        versions = ", ".join(f"{name} ({ver})" for name, _, ver in results)
        st.success(f"Packages — all present: {versions}")
    else:
        for name, ok, detail in results:
            if ok:
                st.success(f"`{name}` — {detail}")
            else:
                st.error(f"`{name}` — **{detail}** (run `uv add {name}`)")
