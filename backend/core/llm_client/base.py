from __future__ import annotations

import json
from abc import ABC, abstractmethod


def coerce_tool_array(value: list | str) -> list:
    """Normalize an array-typed field from a tool_use result.

    Claude occasionally returns an array field as a JSON-encoded string
    instead of a parsed array.
    """
    if isinstance(value, str):
        return json.loads(value)
    return value


def coerce_tool_item(item: dict | str) -> dict:
    """Normalize an item from a tool_use array result."""
    if isinstance(item, str):
        try:
            return json.loads(item)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Expected a JSON object for tool array item, got plain string: {item!r}"
            ) from exc
    return item


class BaseLLMClient(ABC):
    """Abstract base for all LLM provider adapters.

    Callers always pass Anthropic-format tool schemas.
    Adapters translate internally if needed.
    """

    provider: str
    model: str

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system: str | None = None,
        tool_schema: dict | None = None,
        cached_blocks: list[dict] | None = None,
    ) -> str | dict:
        """Send a prompt and return plain text or parsed tool-use dict."""
        ...

    def make_cached_document_blocks(self, text: str) -> list[dict]:
        """Wrap document text for reuse across calls.

        Subclasses that support prompt caching should override this.
        The default returns a plain text block (no caching).
        """
        return [{"type": "text", "text": text}]
