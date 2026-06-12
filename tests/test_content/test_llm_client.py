from __future__ import annotations

import json
import pytest
from backend.content.llm_client import LLMClient


class MockRawClient:
    """Mimics the Anthropic messages.create() interface."""

    def __init__(self, text: str = "", tool_input: dict | None = None):
        self._text = text
        self._tool_input = tool_input

    @property
    def messages(self):
        return self

    def create(self, **kwargs):
        if self._tool_input is not None:
            block = type("Block", (), {"type": "tool_use", "input": self._tool_input})()
            return type("Resp", (), {"content": [block], "stop_reason": "tool_use"})()
        block = type("Block", (), {"type": "text", "text": self._text})()
        return type("Resp", (), {"content": [block], "stop_reason": "end_turn"})()


def make_client(response_text: str = "", tool_input: dict | None = None) -> LLMClient:
    client = LLMClient.__new__(LLMClient)
    client.provider = "anthropic"
    client.model = "claude-sonnet-4-6"
    client._client = MockRawClient(response_text, tool_input)
    return client


def test_generate_returns_string():
    c = make_client("hello world")
    assert c.generate("say hello") == "hello world"


def test_generate_with_tool_schema_returns_dict():
    c = make_client(tool_input={"title": "Test", "summary": "A summary"})
    schema = {"name": "test_tool", "input_schema": {"type": "object"}}
    result = c.generate("prompt", tool_schema=schema)
    assert isinstance(result, dict)
    assert result["title"] == "Test"


def test_make_cached_document_blocks():
    c = make_client("ok")
    blocks = c.make_cached_document_blocks("some text")
    assert len(blocks) == 1
    assert blocks[0]["type"] == "text"
    assert blocks[0]["text"] == "some text"
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}
