from __future__ import annotations

import os

from backend.core.llm_client.base import BaseLLMClient


class LLMFactory:

    @staticmethod
    def create(provider: str | None = None, **kwargs) -> BaseLLMClient:
        """Create an LLM client for the given provider.

        Falls back to AI_TUTOR_LLM_PROVIDER env var (default: anthropic).
        """
        prov = provider or os.environ.get("AI_TUTOR_LLM_PROVIDER", "anthropic")

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
