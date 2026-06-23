from __future__ import annotations

import os
from typing import Any

from backend.core.llm_client.base import BaseLLMClient


class AnthropicAdapter(BaseLLMClient):

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        import anthropic

        self.provider = "anthropic"
        self.model = model or os.environ.get("AI_TUTOR_LLM_MODEL", "claude-sonnet-4-6")
        key = api_key or os.environ.get("AI_TUTOR_LLM_API_KEY", "")
        self._client = anthropic.Anthropic(api_key=key)

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        tool_schema: dict | None = None,
        cached_blocks: list[dict] | None = None,
        topic_context: str | None = None,
        skip_input_guardrails: bool = False,
    ) -> str | dict:
        user_content: list[dict] | str
        if cached_blocks:
            user_content = cached_blocks + [{"type": "text", "text": prompt}]
        else:
            user_content = prompt

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 8192,
            "messages": [{"role": "user", "content": user_content}],
        }

        if system:
            kwargs["system"] = [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ]

        if tool_schema:
            kwargs["tools"] = [tool_schema]
            kwargs["tool_choice"] = {"type": "tool", "name": tool_schema["name"]}

        response = self._client.messages.create(**kwargs)

        if response.stop_reason == "max_tokens":
            raise RuntimeError(
                f"LLM response truncated (hit max_tokens={kwargs['max_tokens']})."
            )

        if tool_schema:
            for block in response.content:
                if block.type == "tool_use":
                    return block.input
            raise RuntimeError("LLM did not return a tool_use block as expected.")

        return response.content[0].text

    def make_cached_document_blocks(self, text: str) -> list[dict]:
        return [
            {
                "type": "text",
                "text": text,
                "cache_control": {"type": "ephemeral"},
            }
        ]
