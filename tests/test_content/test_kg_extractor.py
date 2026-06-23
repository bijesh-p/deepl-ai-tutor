"""Tests for knowledge_graph.extractor — stubbed LLM, edge validation, failure path."""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from typing import Any

import pytest

from backend.content.knowledge_graph.extractor import build_module_graph, extract_edges
from backend.content.knowledge_graph.ontology import RelationType
from backend.content.knowledge_graph.store import KnowledgeGraphStore
from backend.content.models import Diagram, EnrichedTopic, LearningModule, Question, Topic


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_module() -> LearningModule:
    topics = []
    for i, (tid, title, summary) in enumerate([
        ("t1", "Gradient Descent", "Optimisation algorithm"),
        ("t2", "Backpropagation", "Gradient computation via chain rule"),
        ("t3", "Neural Networks", "Layered computational graph"),
    ]):
        topic = Topic(topic_id=tid, title=title, summary=summary, source_section_ids=[], order=i)
        et = EnrichedTopic(
            topic=topic,
            content_md=f"Content for {title}",
            key_takeaways=[f"key {i}"],
            diagrams=[],
            inline_questions=[],
            top_concepts=[title.lower()],
        )
        topics.append(et)
    return LearningModule(
        module_id="mod_test",
        title="Deep Learning Basics",
        source_doc_id="doc1",
        topics=topics,
        created_at="2026-01-01T00:00:00",
    )


class _StubLLM:
    """Returns a fixed edges payload."""

    def __init__(self, edges: list[dict] | None = None, raise_exc: bool = False):
        self._edges = edges or []
        self._raise = raise_exc

    def generate(self, prompt: str, system: str = "", tool_schema: dict | None = None) -> Any:
        if self._raise:
            raise RuntimeError("Simulated LLM failure")
        return {"edges": self._edges}


class _FailLLM(_StubLLM):
    def __init__(self):
        super().__init__(raise_exc=True)


# ---------------------------------------------------------------------------
# extract_edges
# ---------------------------------------------------------------------------

def test_extract_returns_valid_edges():
    module = _make_module()
    llm = _StubLLM([
        {"source_id": "t1", "target_id": "t2", "relation": "PREREQUISITE_OF", "confidence": 0.9},
        {"source_id": "t2", "target_id": "t3", "relation": "RELATED_TO", "confidence": 0.7},
    ])
    edges = extract_edges(module, llm)
    assert len(edges) == 2
    assert edges[0]["relation"] == "PREREQUISITE_OF"


def test_extract_drops_unknown_ids():
    module = _make_module()
    llm = _StubLLM([
        {"source_id": "t1", "target_id": "UNKNOWN_ID", "relation": "RELATED_TO", "confidence": 0.5},
        {"source_id": "t1", "target_id": "t2", "relation": "PREREQUISITE_OF", "confidence": 0.8},
    ])
    edges = extract_edges(module, llm)
    assert len(edges) == 1
    assert edges[0]["source_id"] == "t1"
    assert edges[0]["target_id"] == "t2"


def test_extract_drops_invalid_relation():
    module = _make_module()
    llm = _StubLLM([
        {"source_id": "t1", "target_id": "t2", "relation": "INVENTED_REL", "confidence": 0.5},
    ])
    edges = extract_edges(module, llm)
    assert edges == []


def test_extract_nonfatal_on_llm_failure():
    module = _make_module()
    edges = extract_edges(module, _FailLLM())
    assert edges == []


def test_extract_coerces_json_string_edges():
    """LLM occasionally returns edges as a JSON-encoded string — should coerce."""
    import json
    module = _make_module()

    class _JsonStringLLM:
        def generate(self, *a, **kw):
            return {"edges": json.dumps([
                {"source_id": "t1", "target_id": "t2", "relation": "ELABORATES", "confidence": 0.6}
            ])}

    edges = extract_edges(module, _JsonStringLLM())
    assert len(edges) == 1


def test_extract_drops_self_loops():
    module = _make_module()
    llm = _StubLLM([
        {"source_id": "t1", "target_id": "t1", "relation": "RELATED_TO", "confidence": 0.9},
    ])
    edges = extract_edges(module, llm)
    assert edges == []


# ---------------------------------------------------------------------------
# build_module_graph
# ---------------------------------------------------------------------------

def test_build_module_graph_saves_graphml():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AI_TUTOR_GRAPH_DIR"] = tmp
        module = _make_module()
        store = KnowledgeGraphStore(module.module_id)
        store.add_module(module.title)
        for et in module.topics:
            t = et.topic
            store.add_concept(t.topic_id, t.title, t.summary, t.order)

        llm = _StubLLM([
            {"source_id": "t1", "target_id": "t2", "relation": "PREREQUISITE_OF", "confidence": 0.9},
        ])
        build_module_graph(module, llm, store)

        loaded = KnowledgeGraphStore.load(module.module_id)
        assert loaded is not None
        assert loaded.edge_count() > 0


def test_build_module_graph_nonfatal_on_failure():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AI_TUTOR_GRAPH_DIR"] = tmp
        module = _make_module()
        store = KnowledgeGraphStore(module.module_id)
        store.add_module(module.title)
        # Should not raise even when LLM fails
        build_module_graph(module, _FailLLM(), store)
        # Graph still saved (with only structural edges)
        loaded = KnowledgeGraphStore.load(module.module_id)
        assert loaded is not None
