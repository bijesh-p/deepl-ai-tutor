from __future__ import annotations

from backend.core.llm_client import BaseLLMClient, LLMFactory

# Backward-compatible alias: existing callers can continue using LLMClient()
LLMClient = LLMFactory.create
