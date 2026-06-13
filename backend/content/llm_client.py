from __future__ import annotations

import json

from backend.core.llm_client import BaseLLMClient, LLMFactory

# Backward-compatible alias: existing callers can continue using LLMClient()
LLMClient = LLMFactory.create


def coerce_tool_array(value: list | str) -> list:
    """Normalize an array-typed field from a tool_use result.

    Claude occasionally returns an array field as a JSON-encoded string
    instead of a parsed array.
    """
    if isinstance(value, str):
        return json.loads(value)
    return value


def coerce_tool_item(item: dict | str) -> dict:
    """Normalize an item from a tool_use array result.

    Claude occasionally returns array-of-object items as JSON-encoded
    strings instead of parsed objects.
    """
    if isinstance(item, str):
        try:
            return json.loads(item)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Expected a JSON object for tool array item, got plain string: {item!r}"
            ) from exc
    return item
