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
        topic_context: str | None = None,
        skip_input_guardrails: bool = False,
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
            parsed = json.loads(call.function.arguments)
            if isinstance(parsed, dict):
                self._fix_stringified_values(parsed)
            return parsed

        content = choice.message.content or ""

        if tool_schema and content:
            parsed = self._extract_json(content)
            if isinstance(parsed, dict):
                if "parameters" in parsed:
                    parsed = parsed["parameters"]
                self._fix_stringified_values(parsed)
                return parsed
            raise RuntimeError(
                f"Ollama model did not return valid JSON for tool '{tool_schema['name']}'. "
                f"Raw response: {content[:500]}"
            )

        return content

    @staticmethod
    def _fix_stringified_values(obj: dict) -> None:
        """Small models sometimes stringify nested JSON values. Parse them in-place."""
        for key, value in obj.items():
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, (dict, list)):
                        obj[key] = parsed
                except (json.JSONDecodeError, TypeError):
                    pass

    @staticmethod
    def _extract_json(text: str) -> dict | None:
        """Try to extract a JSON object from model output."""
        # Direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Strip markdown code fences
        import re
        match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Find first { ... } block
        start = text.find("{")
        if start != -1:
            depth = 0
            for i in range(start, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start : i + 1])
                        except json.JSONDecodeError:
                            break
        return None

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
