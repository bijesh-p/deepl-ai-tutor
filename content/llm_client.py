from __future__ import annotations

import os
import json
from typing import Any


class LLMClient:
    """Provider-agnostic LLM interface. Phase 1 implements Anthropic only."""

    def __init__(
        self,
        provider: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self.provider = provider or os.environ.get("AI_TUTOR_LLM_PROVIDER", "anthropic")
        self.api_key = api_key or os.environ.get("AI_TUTOR_LLM_API_KEY", "")
        self.model = model or os.environ.get("AI_TUTOR_LLM_MODEL", "claude-sonnet-4-6")

        if self.provider == "anthropic":
            self._client = self._make_anthropic_client()
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider!r}. Phase 1 supports 'anthropic' only.")

    def _make_anthropic_client(self):
        import anthropic
        return anthropic.Anthropic(api_key=self.api_key)

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        tool_schema: dict | None = None,
        cached_blocks: list[dict] | None = None,
    ) -> str | dict:
        """Send a prompt and return a plain string or parsed dict (when tool_schema given).

        Args:
            prompt: User-turn content.
            system: System prompt text.
            tool_schema: If provided, the LLM is asked to call this tool and
                         the parsed arguments dict is returned.
            cached_blocks: Pre-built content blocks with cache_control already
                           set. When provided, they are prepended to the user
                           turn so long context is cached across calls.
        """
        if self.provider == "anthropic":
            return self._generate_anthropic(prompt, system, tool_schema, cached_blocks)
        raise NotImplementedError(self.provider)

    def _generate_anthropic(
        self,
        prompt: str,
        system: str | None,
        tool_schema: dict | None,
        cached_blocks: list[dict] | None,
    ) -> str | dict:
        import anthropic

        # Build user message — prepend cached blocks if supplied
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
                f"LLM response was truncated (hit max_tokens={kwargs['max_tokens']}). "
                "The prompt or expected output may be too large."
            )

        if tool_schema:
            for block in response.content:
                if block.type == "tool_use":
                    return block.input
            raise RuntimeError("LLM did not return a tool_use block as expected.")

        return response.content[0].text

    def make_cached_document_blocks(self, text: str) -> list[dict]:
        """Wrap document text in a cache-control block for reuse across calls."""
        return [
            {
                "type": "text",
                "text": text,
                "cache_control": {"type": "ephemeral"},
            }
        ]


def coerce_tool_array(value: list | str) -> list:
    """Normalize an array-typed field from a tool_use result.

    Claude occasionally returns an array field as a JSON-encoded string
    instead of a parsed array. Parse those back into lists so callers can
    iterate over items uniformly.
    """
    if isinstance(value, str):
        return json.loads(value)
    return value


def coerce_tool_item(item: dict | str) -> dict:
    """Normalize an item from a tool_use array result.

    Claude occasionally returns array-of-object items as JSON-encoded
    strings instead of parsed objects. Parse those back into dicts so
    callers can use dict access uniformly.
    """
    if isinstance(item, str):
        try:
            return json.loads(item)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Expected a JSON object for tool array item, got plain string: {item!r}"
            ) from exc
    return item
