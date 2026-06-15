"""Tests for backend.core.mcp_client against the lightweight assessment_server.

assessment_server has no heavy dependencies (no ChromaDB / sentence-transformers),
making it a good smoke test for the generic MCPClient subprocess + session
mechanism shared by all servers.
"""
from __future__ import annotations

import json

import pytest

from backend.core.mcp_client import get_client


def test_call_assessment_server_evaluate_taxonomy():
    client = get_client("assessment_server")
    questions = [{"question_text": "Why does X happen?", "bloom_level": "analyze"}]

    result_json = client.call("evaluate_taxonomy", questions_json=json.dumps(questions))
    result = json.loads(result_json)

    assert result[0]["bloom_level"] == "analyze"
    assert result[0]["difficulty"] == "medium"


def test_get_client_returns_singleton():
    assert get_client("assessment_server") is get_client("assessment_server")


def test_unknown_server_raises():
    with pytest.raises(ValueError, match="Unknown MCP server"):
        get_client("not_a_server")
