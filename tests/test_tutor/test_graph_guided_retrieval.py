"""Tests for graph_guided_context — graph present vs absent, mode behaviour, fallback."""
from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from backend.content.knowledge_graph.ontology import RelationType
from backend.content.knowledge_graph.store import KnowledgeGraphStore
from backend.content.knowledge_graph.retrieval import graph_guided_context


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store_with_edges(tmp: str, module_id: str = "mod1") -> KnowledgeGraphStore:
    os.environ["AI_TUTOR_GRAPH_DIR"] = tmp
    store = KnowledgeGraphStore(module_id)
    store.add_module("Test Module")
    store.add_concept("t1", "Gradient Descent", "Optimisation algorithm", 0)
    store.add_concept("t2", "Backpropagation", "Chain rule gradient computation", 1)
    store.add_concept("t3", "Neural Networks", "Layered function", 2)
    store.add_edge("t1", "t2", RelationType.PREREQUISITE_OF, weight=0.9, source="llm")
    store.add_edge("t2", "t3", RelationType.RELATED_TO, weight=0.8, source="llm")
    store.save()
    return store


def _fake_mcp_response(docs: list[str]) -> str:
    return json.dumps({"documents": [docs]})


# ---------------------------------------------------------------------------
# Graph absent → pure vector fallback
# ---------------------------------------------------------------------------

def test_graph_absent_falls_back_to_vector():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AI_TUTOR_GRAPH_DIR"] = tmp

        fake_client = MagicMock()
        fake_client.call.return_value = _fake_mcp_response(["vector result"])

        with patch("backend.core.mcp_client.get_client", return_value=fake_client):
            result = graph_guided_context("no_such_module", "t1", "query about gradients")

        assert "vector result" in result


# ---------------------------------------------------------------------------
# Graph present — mode "present"
# ---------------------------------------------------------------------------

def test_present_mode_returns_related_and_prereqs():
    with tempfile.TemporaryDirectory() as tmp:
        _make_store_with_edges(tmp)

        fake_client = MagicMock()
        # Return different content per topic_id filter — call() is called with keyword args
        def _side_effect(*args, **kwargs):
            flt = kwargs.get("where_filter", {})
            tid = flt.get("topic_id", "")
            if tid == "t1":
                return _fake_mcp_response(["def of gradient descent"])
            if tid == "t2":
                return _fake_mcp_response(["def of backprop"])
            # vector top-up call (no topic_id filter)
            return _fake_mcp_response(["vector fallback"])

        fake_client.call.side_effect = _side_effect

        with patch("backend.core.mcp_client.get_client", return_value=fake_client):
            result = graph_guided_context("mod1", "t3", "neural networks", mode="present")

        assert "def of backprop" in result


# ---------------------------------------------------------------------------
# Graph present — mode "hint" (prereqs first)
# ---------------------------------------------------------------------------

def test_hint_mode_prioritises_prerequisites():
    with tempfile.TemporaryDirectory() as tmp:
        _make_store_with_edges(tmp)

        fake_client = MagicMock()
        fake_client.call.return_value = _fake_mcp_response(["prereq content"])

        with patch("backend.core.mcp_client.get_client", return_value=fake_client):
            result = graph_guided_context("mod1", "t2", "struggling with backprop", mode="hint")

        assert result != ""


# ---------------------------------------------------------------------------
# Graph present — mode "simplify" (depth-2 prereqs in teaching order)
# ---------------------------------------------------------------------------

def test_simplify_mode_returns_deep_prereqs():
    with tempfile.TemporaryDirectory() as tmp:
        _make_store_with_edges(tmp)
        # Add another prereq level: t0 → t1 → t2
        store = KnowledgeGraphStore.load("mod1")
        store.add_concept("t0", "Calculus Basics", "Derivatives", -1)
        store.add_edge("t0", "t1", RelationType.PREREQUISITE_OF, weight=0.95, source="llm")
        store.save()

        fake_client = MagicMock()
        fake_client.call.return_value = _fake_mcp_response(["deep prereq"])

        with patch("backend.core.mcp_client.get_client", return_value=fake_client):
            result = graph_guided_context("mod1", "t2", "simplify backprop", mode="simplify")

        assert result != ""


# ---------------------------------------------------------------------------
# topic_id=None → vector fallback
# ---------------------------------------------------------------------------

def test_none_topic_id_falls_back_to_vector():
    with tempfile.TemporaryDirectory() as tmp:
        _make_store_with_edges(tmp)

        fake_client = MagicMock()
        fake_client.call.return_value = _fake_mcp_response(["vector only"])

        with patch("backend.core.mcp_client.get_client", return_value=fake_client):
            result = graph_guided_context("mod1", None, "some query")

        assert "vector only" in result


# ---------------------------------------------------------------------------
# Exception in retrieval → returns "" (never raises)
# ---------------------------------------------------------------------------

def test_exception_returns_empty_string():
    with tempfile.TemporaryDirectory() as tmp:
        _make_store_with_edges(tmp)

        with patch("backend.core.mcp_client.get_client", side_effect=RuntimeError("MCP down")):
            result = graph_guided_context("mod1", "t2", "some query")

        assert result == ""
