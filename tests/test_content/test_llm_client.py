from __future__ import annotations

import pytest
from backend.core.llm_client import BaseLLMClient, LLMFactory
from backend.core.llm_client.adapters.anthropic_adapter import AnthropicAdapter


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


def make_adapter(response_text: str = "", tool_input: dict | None = None) -> AnthropicAdapter:
    adapter = AnthropicAdapter.__new__(AnthropicAdapter)
    adapter.provider = "anthropic"
    adapter.model = "claude-sonnet-4-6"
    adapter._client = MockRawClient(response_text, tool_input)
    return adapter


def test_generate_returns_string():
    c = make_adapter("hello world")
    assert c.generate("say hello") == "hello world"


def test_generate_with_tool_schema_returns_dict():
    c = make_adapter(tool_input={"title": "Test", "summary": "A summary"})
    schema = {"name": "test_tool", "input_schema": {"type": "object"}}
    result = c.generate("prompt", tool_schema=schema)
    assert isinstance(result, dict)
    assert result["title"] == "Test"


def test_make_cached_document_blocks():
    c = make_adapter("ok")
    blocks = c.make_cached_document_blocks("some text")
    assert len(blocks) == 1
    assert blocks[0]["type"] == "text"
    assert blocks[0]["text"] == "some text"
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}


def test_factory_unknown_provider():
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        LLMFactory.create("nonexistent")


def test_base_class_is_abstract():
    with pytest.raises(TypeError):
        BaseLLMClient()


def test_ollama_tool_schema_translation():
    from backend.core.llm_client.adapters.ollama_adapter import OllamaAdapter
    anthropic_schema = {
        "name": "get_weather",
        "description": "Get current weather",
        "input_schema": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
        },
    }
    result = OllamaAdapter._translate_tool_schema(anthropic_schema)
    assert result["type"] == "function"
    assert result["function"]["name"] == "get_weather"
    assert result["function"]["parameters"]["type"] == "object"
