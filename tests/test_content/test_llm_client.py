from __future__ import annotations

import json
import pytest
from content.llm_client import LLMClient, Provider


class MockRawClient:
    """Mimics the Anthropic messages.create() interface."""

    def __init__(self, text: str):
        self._text = text

    @property
    def messages(self):
        return self

    def create(self, **kwargs):
        class _Resp:
            content = [type("Block", (), {"text": self._text})()]
        return _Resp()


def make_client(response_text: str) -> LLMClient:
    client = LLMClient.__new__(LLMClient)
    client.provider = Provider.ANTHROPIC
    client.model = "claude-opus-4-8"
    client._client = MockRawClient(response_text)
    return client


def test_generate_returns_string():
    c = make_client("hello world")
    assert c.generate("say hello") == "hello world"


def test_generate_parses_json_with_schema():
    payload = json.dumps({"title": "Test", "summary": "A summary"})
    c = make_client(payload)
    result = c.generate("prompt", response_schema={"type": "object"})
    assert isinstance(result, dict)
    assert result["title"] == "Test"


def test_generate_strips_markdown_fences():
    payload = "```json\n" + json.dumps({"key": "value"}) + "\n```"
    c = make_client(payload)
    result = c.generate("prompt", response_schema={"type": "object"})
    assert result["key"] == "value"


def test_provider_enum_values():
    assert Provider.ANTHROPIC.value == "anthropic"
    assert Provider.PORTKEY.value == "portkey"


def test_build_client_raises_for_portkey_without_virtual_key():
    with pytest.raises((ValueError, Exception)):
        LLMClient(
            provider=Provider.PORTKEY,
            api_key="fake",
            model="claude-opus-4-8",
            portkey_virtual_key=None,
        )
