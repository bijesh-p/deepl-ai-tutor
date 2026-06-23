"""Tests for KnowledgeGraphStore — round-trip, traversals, cycle-breaking."""
from __future__ import annotations

import os
import tempfile

import pytest

from backend.content.knowledge_graph.ontology import RelationType
from backend.content.knowledge_graph.store import KnowledgeGraphStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store(module_id: str = "mod1", tmp_dir: str | None = None) -> KnowledgeGraphStore:
    if tmp_dir:
        os.environ["AI_TUTOR_GRAPH_DIR"] = tmp_dir
    store = KnowledgeGraphStore(module_id)
    store.add_module("Test Module")
    store.add_concept("t1", "Concept A", "Summary A", 0)
    store.add_concept("t2", "Concept B", "Summary B", 1)
    store.add_concept("t3", "Concept C", "Summary C", 2)
    return store


# ---------------------------------------------------------------------------
# Basic add / idempotency
# ---------------------------------------------------------------------------

def test_add_concept_idempotent():
    store = KnowledgeGraphStore("mod")
    store.add_concept("t1", "A", "S", 0)
    store.add_concept("t1", "A updated", "S updated", 0)  # second add — same node
    assert store.node_count() == 1


def test_add_term_returns_slug():
    store = KnowledgeGraphStore("mod")
    nid = store.add_term("Neural Network")
    assert nid == "neural_network"
    # second call — idempotent
    nid2 = store.add_term("Neural Network")
    assert nid == nid2
    assert store.node_count() == 1


def test_add_edge_idempotent():
    store = KnowledgeGraphStore("mod")
    store.add_concept("t1", "A", "S", 0)
    store.add_concept("t2", "B", "S", 1)
    store.add_edge("t1", "t2", RelationType.PREREQUISITE_OF)
    store.add_edge("t1", "t2", RelationType.PREREQUISITE_OF)  # duplicate
    assert store.edge_count() == 1


# ---------------------------------------------------------------------------
# GraphML round-trip
# ---------------------------------------------------------------------------

def test_save_load_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AI_TUTOR_GRAPH_DIR"] = tmp
        store = _make_store("mod_rt", tmp)
        store.add_edge("t1", "t2", RelationType.PREREQUISITE_OF, weight=0.9)
        store.add_edge("t2", "t3", RelationType.RELATED_TO)
        store.save()

        loaded = KnowledgeGraphStore.load("mod_rt")
        assert loaded is not None
        assert loaded.node_count() == store.node_count()
        assert loaded.edge_count() == store.edge_count()


def test_load_missing_returns_none():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["AI_TUTOR_GRAPH_DIR"] = tmp
        result = KnowledgeGraphStore.load("nonexistent_module")
        assert result is None


# ---------------------------------------------------------------------------
# Traversal: prerequisites
# ---------------------------------------------------------------------------

def test_prerequisites_depth1():
    store = KnowledgeGraphStore("mod")
    store.add_concept("t1", "A", "S", 0)
    store.add_concept("t2", "B", "S", 1)
    # t1 must be learned before t2
    store.add_edge("t1", "t2", RelationType.PREREQUISITE_OF)
    assert "t1" in store.prerequisites("t2", depth=1)


def test_prerequisites_depth2():
    store = KnowledgeGraphStore("mod")
    for i, n in enumerate(["t1", "t2", "t3"]):
        store.add_concept(n, f"C{i}", "S", i)
    store.add_edge("t1", "t2", RelationType.PREREQUISITE_OF)
    store.add_edge("t2", "t3", RelationType.PREREQUISITE_OF)
    prereqs = store.prerequisites("t3", depth=2)
    assert "t1" in prereqs and "t2" in prereqs


def test_prerequisites_no_prereqs():
    store = _make_store()
    assert store.prerequisites("t1") == []


# ---------------------------------------------------------------------------
# Traversal: related
# ---------------------------------------------------------------------------

def test_related_bidirectional():
    store = _make_store()
    store.add_edge("t1", "t2", RelationType.RELATED_TO)
    # t2 is related to t1 (reverse direction should also be returned)
    assert "t1" in store.related("t2")


def test_related_k_limit():
    store = KnowledgeGraphStore("mod")
    for i in range(5):
        store.add_concept(f"t{i}", f"C{i}", "S", i)
    for i in range(1, 5):
        store.add_edge("t0", f"t{i}", RelationType.RELATED_TO)
    assert len(store.related("t0", k=2)) == 2


# ---------------------------------------------------------------------------
# Traversal: teaching_order
# ---------------------------------------------------------------------------

def test_teaching_order_follows_prerequisites():
    store = KnowledgeGraphStore("mod")
    store.add_concept("t1", "A", "S", 0)
    store.add_concept("t2", "B", "S", 1)
    store.add_concept("t3", "C", "S", 2)
    store.add_edge("t1", "t2", RelationType.PREREQUISITE_OF)
    store.add_edge("t2", "t3", RelationType.PREREQUISITE_OF)
    order = store.teaching_order()
    assert order.index("t1") < order.index("t2") < order.index("t3")


def test_teaching_order_fallback_to_follows_order():
    store = _make_store()  # no PREREQUISITE_OF edges
    order = store.teaching_order()
    assert set(order) == {"t1", "t2", "t3"}


# ---------------------------------------------------------------------------
# Cycle breaking
# ---------------------------------------------------------------------------

def test_break_prerequisite_cycles():
    store = KnowledgeGraphStore("mod")
    store.add_concept("t1", "A", "S", 0)
    store.add_concept("t2", "B", "S", 1)
    # Artificially create a cycle
    store.add_edge("t1", "t2", RelationType.PREREQUISITE_OF, weight=0.9)
    store.add_edge("t2", "t1", RelationType.PREREQUISITE_OF, weight=0.4)  # lower weight → removed
    removed = store.break_prerequisite_cycles()
    assert removed >= 1
    # After breaking, no cycles remain
    import networkx as nx
    prereq_g = nx.DiGraph(
        (u, v)
        for u, v, d in store._g.edges(data=True)
        if d.get("relation") == "PREREQUISITE_OF"
    )
    assert nx.is_directed_acyclic_graph(prereq_g)
