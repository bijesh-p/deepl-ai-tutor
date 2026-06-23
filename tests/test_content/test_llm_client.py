from __future__ import annotations

import json

import pytest
from backend.core.llm_client import BaseLLMClient, LLMFactory
from backend.core.llm_client.adapters.anthropic_adapter import AnthropicAdapter
from backend.core.llm_client.adapters.ollama_adapter import OllamaAdapter
from backend.core.llm_client.adapters.portkey_adapter import PortkeyAdapter


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


def test_factory_wraps_adapter_in_guardrails(monkeypatch):
    monkeypatch.setenv("AI_TUTOR_LLM_API_KEY", "test-key")
    from backend.core.guardrails import GuardrailedLLMClient

    client = LLMFactory.create("anthropic")
    assert isinstance(client, GuardrailedLLMClient)
    assert client.provider == "anthropic"
    assert client.model


def test_base_class_is_abstract():
    with pytest.raises(TypeError):
        BaseLLMClient()


def test_ollama_tool_schema_translation():
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


# --- PortkeyAdapter ---------------------------------------------------------


def make_portkey_adapter(response_text: str = "", tool_input: dict | None = None) -> PortkeyAdapter:
    adapter = PortkeyAdapter.__new__(PortkeyAdapter)
    adapter.provider = "portkey"
    adapter.model = "@vertexai-global/anthropic.claude-sonnet-4-6"
    adapter._client = MockRawClient(response_text, tool_input)
    return adapter


def test_portkey_generate_returns_string():
    c = make_portkey_adapter("hello from portkey")
    assert c.generate("say hello") == "hello from portkey"


def test_portkey_generate_with_tool_schema_returns_dict():
    c = make_portkey_adapter(tool_input={"title": "Test", "summary": "A summary"})
    schema = {"name": "test_tool", "input_schema": {"type": "object"}}
    result = c.generate("prompt", tool_schema=schema)
    assert isinstance(result, dict)
    assert result["title"] == "Test"


def test_portkey_make_cached_document_blocks():
    c = make_portkey_adapter("ok")
    blocks = c.make_cached_document_blocks("some text")
    assert len(blocks) == 1
    assert blocks[0]["type"] == "text"
    assert blocks[0]["text"] == "some text"
    assert blocks[0]["cache_control"] == {"type": "ephemeral"}


# --- OllamaAdapter -----------------------------------------------------------


class MockOllamaClient:
    """Mimics the OpenAI chat.completions.create() interface."""

    def __init__(self, content: str = "", tool_calls=None):
        self._content = content
        self._tool_calls = tool_calls

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        message = type(
            "Message", (), {"content": self._content, "tool_calls": self._tool_calls}
        )()
        choice = type("Choice", (), {"message": message})()
        return type("Resp", (), {"choices": [choice]})()


def make_ollama_adapter(content: str = "", tool_calls=None) -> OllamaAdapter:
    adapter = OllamaAdapter.__new__(OllamaAdapter)
    adapter.provider = "ollama"
    adapter.model = "llama3.2"
    adapter._client = MockOllamaClient(content, tool_calls)
    return adapter


def _make_tool_call(arguments: dict) -> object:
    function = type("Function", (), {"arguments": json.dumps(arguments)})()
    return type("ToolCall", (), {"function": function})()


def test_ollama_generate_plain_text():
    c = make_ollama_adapter(content="hello from ollama")
    assert c.generate("say hi") == "hello from ollama"


def test_ollama_generate_with_tool_calls():
    tool_call = _make_tool_call({"title": "X", "nested": json.dumps({"a": 1})})
    c = make_ollama_adapter(tool_calls=[tool_call])
    schema = {"name": "test_tool", "input_schema": {"type": "object"}}
    result = c.generate("prompt", tool_schema=schema)
    assert result["title"] == "X"
    assert result["nested"] == {"a": 1}


def test_ollama_generate_json_fallback_plain():
    c = make_ollama_adapter(content='{"title": "Y"}')
    schema = {"name": "test_tool", "input_schema": {"type": "object"}}
    result = c.generate("prompt", tool_schema=schema)
    assert result["title"] == "Y"


def test_ollama_generate_json_fallback_fenced():
    c = make_ollama_adapter(content='Here is the result:\n```json\n{"title": "Z"}\n```')
    schema = {"name": "test_tool", "input_schema": {"type": "object"}}
    result = c.generate("prompt", tool_schema=schema)
    assert result["title"] == "Z"


def test_ollama_generate_json_fallback_brace_matched():
    c = make_ollama_adapter(content='Sure! {"title": "W"} is the answer.')
    schema = {"name": "test_tool", "input_schema": {"type": "object"}}
    result = c.generate("prompt", tool_schema=schema)
    assert result["title"] == "W"


def test_ollama_generate_json_fallback_unwraps_parameters():
    c = make_ollama_adapter(content='{"parameters": {"title": "V"}}')
    schema = {"name": "test_tool", "input_schema": {"type": "object"}}
    result = c.generate("prompt", tool_schema=schema)
    assert result["title"] == "V"
