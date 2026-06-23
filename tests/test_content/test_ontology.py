"""Tests for knowledge_graph.ontology — enums and slug helper."""
from backend.content.knowledge_graph.ontology import NodeType, RelationType, slug


def test_node_type_values():
    assert NodeType.MODULE.value == "MODULE"
    assert NodeType.CONCEPT.value == "CONCEPT"
    assert NodeType.TERM.value == "TERM"


def test_relation_type_values():
    expected = {"PART_OF", "FOLLOWS", "PREREQUISITE_OF", "RELATED_TO", "ELABORATES", "MENTIONS", "DEFINES"}
    assert {r.value for r in RelationType} == expected


def test_slug_basic():
    assert slug("Neural Network") == "neural_network"


def test_slug_strips_punctuation():
    assert slug("back-propagation!") == "back_propagation"


def test_slug_stable():
    assert slug("Gradient Descent") == slug("gradient descent")


def test_slug_collapses_separators():
    assert slug("  hello   world  ") == "hello_world"


def test_slug_empty_fallback():
    assert slug("!!!") == "term"


def test_slug_alphanumeric():
    assert slug("layer_1") == "layer_1"
