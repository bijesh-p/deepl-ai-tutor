from __future__ import annotations

import json
import os
from typing import Any

from backend.core.llm_client.base import BaseLLMClient


class OllamaAdapter(BaseLLMClient):

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
    ):
        from openai import OpenAI

        self.provider = "ollama"
        self.model = model or os.environ.get("AI_TUTOR_LLM_MODEL", "llama3.2")
        url = base_url or os.environ.get(
            "AI_TUTOR_OLLAMA_BASE_URL", "http://localhost:11434/v1"
        )
        self._client = OpenAI(base_url=url, api_key="ollama")

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        tool_schema: dict | None = None,
        cached_blocks: list[dict] | None = None,
    ) -> str | dict:
        messages: list[dict[str, Any]] = []

        if system:
            messages.append({"role": "system", "content": system})

        user_text = prompt
        if cached_blocks:
            prefix = "\n\n".join(
                b["text"] for b in cached_blocks if b.get("type") == "text"
            )
            user_text = f"{prefix}\n\n{prompt}"

        messages.append({"role": "user", "content": user_text})

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }

        if tool_schema:
            kwargs["tools"] = [self._translate_tool_schema(tool_schema)]
            kwargs["tool_choice"] = {
                "type": "function",
                "function": {"name": tool_schema["name"]},
            }

        response = self._client.chat.completions.create(**kwargs)
        choice = response.choices[0]

        if tool_schema and choice.message.tool_calls:
            call = choice.message.tool_calls[0]
            return json.loads(call.function.arguments)

        return choice.message.content or ""

    @staticmethod
    def _translate_tool_schema(anthropic_schema: dict) -> dict:
        """Convert Anthropic tool schema to OpenAI function-calling format."""
        return {
            "type": "function",
            "function": {
                "name": anthropic_schema["name"],
                "description": anthropic_schema.get("description", ""),
                "parameters": anthropic_schema.get("input_schema", {}),
            },
        }
