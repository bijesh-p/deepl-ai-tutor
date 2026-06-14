from __future__ import annotations

import os

from backend.core.llm_client.base import BaseLLMClient


def _get_session_state():
    """Read provider/model from Streamlit session_state if available."""
    try:
        import streamlit as st
        if hasattr(st, "session_state"):
            return (
                st.session_state.get("llm_provider"),
                st.session_state.get("llm_model"),
            )
    except Exception:
        pass
    return None, None


class LLMFactory:

    @staticmethod
    def create(provider: str | None = None, **kwargs) -> BaseLLMClient:
        """Create an LLM client for the given provider.

        Resolution order for provider/model:
          1. Explicit arguments
          2. Streamlit session_state (llm_provider / llm_model)
          3. Environment variables
        """
        ss_provider, ss_model = _get_session_state()
        prov = provider or ss_provider or os.environ.get("AI_TUTOR_LLM_PROVIDER", "anthropic")

        if "model" not in kwargs and ss_model:
            kwargs["model"] = ss_model

        if prov == "anthropic":
            from backend.core.llm_client.adapters.anthropic_adapter import AnthropicAdapter
            return AnthropicAdapter(**kwargs)

        if prov == "portkey":
            from backend.core.llm_client.adapters.portkey_adapter import PortkeyAdapter
            return PortkeyAdapter(**kwargs)

        if prov == "ollama":
            from backend.core.llm_client.adapters.ollama_adapter import OllamaAdapter
            return OllamaAdapter(**kwargs)

        raise ValueError(
            f"Unknown LLM provider: {prov!r}. "
            "Supported: 'anthropic', 'portkey', 'ollama'."
        )
