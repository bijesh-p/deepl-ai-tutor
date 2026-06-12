from __future__ import annotations

import os
from typing import Any

from backend.core.llm_client.base import BaseLLMClient


class PortkeyAdapter(BaseLLMClient):

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        virtual_key: str | None = None,
    ):
        from portkey_ai import Portkey

        self.provider = "portkey"
        self.model = model or os.environ.get("AI_TUTOR_LLM_MODEL", "claude-sonnet-4-6")
        key = api_key or os.environ.get("AI_TUTOR_PORTKEY_API_KEY", "")
        vk = virtual_key or os.environ.get("AI_TUTOR_PORTKEY_VIRTUAL_KEY", "")
        if not vk:
            raise ValueError(
                "Portkey requires a virtual key. "
                "Set AI_TUTOR_PORTKEY_VIRTUAL_KEY in .env or pass virtual_key=."
            )
        self._client = Portkey(api_key=key, virtual_key=vk)

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

        response = self._client.chat.completions.create(**kwargs)

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
