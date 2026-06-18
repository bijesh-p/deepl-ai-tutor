from __future__ import annotations

import os
from typing import Any

from backend.core.llm_client.base import BaseLLMClient

PORTKEY_BASE_URL = "https://api.portkey.ai"


class PortkeyAdapter(BaseLLMClient):

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        import anthropic

        self.provider = "portkey"
        self.model = model or os.environ.get(
            "AI_TUTOR_PORTKEY_MODEL",
            "@vertexai-global/anthropic.claude-sonnet-4-6",
        )
        portkey_key = api_key or os.environ.get("PORTKEY_API_KEY", "")
        if not portkey_key:
            raise ValueError(
                "Portkey requires PORTKEY_API_KEY. Set it in .env."
            )
        self._client = anthropic.Anthropic(
            api_key="dummy",
            base_url=PORTKEY_BASE_URL,
            default_headers={"x-portkey-api-key": portkey_key},
        )

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        tool_schema: dict | None = None,
        cached_blocks: list[dict] | None = None,
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
