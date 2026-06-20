from __future__ import annotations

import json

from backend.interactive_tutor import graph


class _MockLLM:
    """Captures generate() calls and returns a fixed response."""

    def __init__(self, response: str = "mock response"):
        self.response = response
        self.calls: list[dict] = []

    def generate(self, prompt, **kwargs):
        self.calls.append({"prompt": prompt, **kwargs})
        return self.response


class _StubMCPClient:
    """Mimics MCPClient.call() for storage_server.query_vector_db."""

    def __init__(self, response_json: str):
        self.response_json = response_json

    def call(self, tool_name, **kwargs):
        return self.response_json


def _vector_db_response(text: str) -> str:
    return json.dumps({"documents": [[text]], "ids": [["mod-1:topic-1"]], "distances": [[0.1]]})


def test_provide_hint_uses_retrieved_context(monkeypatch):
    retrieved = "Chlorophyll absorbs light energy inside chloroplasts."
    monkeypatch.setattr(
        "backend.core.mcp_client.get_client",
        lambda server_name: _StubMCPClient(_vector_db_response(retrieved)),
    )
    mock_llm = _MockLLM("Here's a hint about chlorophyll.")
    monkeypatch.setattr(graph, "_get_llm", lambda: mock_llm)

    state: graph.GraphState = {
        "current_concept": "Photosynthesis",
        "module_id": "mod-1",
        "feedback": "confused about chlorophyll",
        "chat_history": [],
    }

    result = graph.provide_hint(state)

    assert mock_llm.calls, "LLM was not called"
    assert retrieved in mock_llm.calls[0]["prompt"]
    assert result["chat_history"][-1]["content"] == "Hint: Here's a hint about chlorophyll."


def test_present_concept_chromadb_fallback(monkeypatch):
    retrieved = "Photosynthesis converts light into chemical energy stored in glucose."
    monkeypatch.setattr(
        "backend.core.mcp_client.get_client",
        lambda server_name: _StubMCPClient(_vector_db_response(retrieved)),
    )
    mock_llm = _MockLLM("Adapted explanation of photosynthesis.")
    monkeypatch.setattr(graph, "_get_llm", lambda: mock_llm)

    state: graph.GraphState = {
        "current_concept": "Photosynthesis",
        "module_id": "mod-1",
        "presentation_depth": "intermediate",
        "enriched_topic": None,
        "concept_content": "",
        "audio_enabled": False,
        "chat_history": [],
    }

    result = graph.present_concept(state)

    assert result["concept_content"] == "Adapted explanation of photosynthesis."
    # The retrieved chunk must appear in a plain-text depth-adaptation call
    # (no tool_schema). The inline _try_diagram call comes first and uses a
    # tool_schema; depth-adaptation must follow without one.
    assert mock_llm.calls
    adapt_calls = [c for c in mock_llm.calls if c.get("tool_schema") is None]
    assert adapt_calls, "No plain-text depth-adaptation call was made"
    assert retrieved in adapt_calls[0]["prompt"]


def test_provide_hint_chromadb_error_is_non_fatal(monkeypatch):
    def _raise(server_name):
        raise RuntimeError("storage_server unavailable")

    monkeypatch.setattr("backend.core.mcp_client.get_client", _raise)
    mock_llm = _MockLLM("Here's a hint anyway.")
    monkeypatch.setattr(graph, "_get_llm", lambda: mock_llm)

    state: graph.GraphState = {
        "current_concept": "Photosynthesis",
        "module_id": "mod-1",
        "feedback": "confused about chlorophyll",
        "chat_history": [],
    }

    result = graph.provide_hint(state)

    assert result["chat_history"][-1]["content"] == "Hint: Here's a hint anyway."
