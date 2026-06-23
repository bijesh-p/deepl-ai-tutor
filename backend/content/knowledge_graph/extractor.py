"""LLM-based relation extractor for the per-module knowledge graph.

Builds typed edges (PREREQUISITE_OF, RELATED_TO, ELABORATES, MENTIONS, DEFINES)
between concepts in a LearningModule by sending a compact concept catalogue to
the LLM and parsing its emit_knowledge_graph tool response.

Non-fatal: any LLM/parse failure logs and returns [], so the tutor still works
with only the deterministic structural edges already in the store.
"""
from __future__ import annotations

import logging
from typing import Any

from backend.content.knowledge_graph.ontology import RelationType, slug
from backend.content.knowledge_graph.store import KnowledgeGraphStore
from backend.content.models import LearningModule

_log = logging.getLogger(__name__)

# Relations the LLM is allowed to emit (structural ones are added by pipeline)
_LLM_RELATIONS = {r.value for r in (
    RelationType.PREREQUISITE_OF,
    RelationType.RELATED_TO,
    RelationType.ELABORATES,
    RelationType.MENTIONS,
    RelationType.DEFINES,
)}

_EXTRACT_SCHEMA = {
    "name": "emit_knowledge_graph",
    "description": "Typed relationships between the module's concepts.",
    "input_schema": {
        "type": "object",
        "properties": {
            "edges": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "source_id": {"type": "string"},
                        "target_id": {"type": "string"},
                        "relation": {
                            "type": "string",
                            "enum": list(_LLM_RELATIONS),
                        },
                        "confidence": {"type": "number"},
                    },
                    "required": ["source_id", "target_id", "relation", "confidence"],
                },
            }
        },
        "required": ["edges"],
    },
}

_EXTRACT_SYSTEM = (
    "You are a knowledge-engineering assistant. "
    "Given a compact catalogue of concepts from a learning module, "
    "emit typed relationships between them. "
    "Use PREREQUISITE_OF when a student must understand concept A before B. "
    "Use RELATED_TO for symmetric semantic links. "
    "Use ELABORATES when A is a deeper or specialised view of B. "
    "Use MENTIONS when a concept references a specific term. "
    "Use DEFINES when a concept is the canonical definition of a term. "
    "Only emit edges between the node ids provided. "
    "Confidence values should reflect how strongly the relationship holds (0–1)."
)


def _build_catalogue(module: LearningModule) -> tuple[str, set[str], dict[str, set[str]]]:
    """Build a compact text catalogue + valid id sets for validation.

    Returns:
        catalogue_text: text sent to LLM
        concept_ids: set of valid topic_id strings
        term_slugs: mapping topic_id → set of slug ids for terms it mentions
    """
    lines: list[str] = [f"Module: {module.title}\n"]
    concept_ids: set[str] = set()
    term_slugs: dict[str, set[str]] = {}

    for et in module.topics:
        t = et.topic
        concept_ids.add(t.topic_id)
        terms = set(et.top_concepts or []) | set(et.key_takeaways or [])
        slugged = {slug(term) for term in terms if term.strip()}
        term_slugs[t.topic_id] = slugged

        lines.append(
            f"- concept_id: {t.topic_id}\n"
            f"  title: {t.title}\n"
            f"  summary: {t.summary}\n"
            f"  order: {t.order}\n"
            f"  terms: {', '.join(sorted(slugged)) or '(none)'}\n"
        )

    return "\n".join(lines), concept_ids, term_slugs


def _coerce_edges(raw: Any) -> list[dict]:
    """Normalise the edges field — Claude occasionally returns a JSON-encoded string."""
    if isinstance(raw, str):
        import json
        try:
            raw = json.loads(raw)
        except Exception:
            return []
    if isinstance(raw, list):
        return raw
    return []


def extract_edges(module: LearningModule, llm, tracer=None) -> list[dict]:
    """Call the LLM to extract typed edges for the module.

    Returns a list of raw edge dicts (source_id, target_id, relation, confidence).
    Unknown ids are dropped. On failure returns [].
    """
    catalogue, concept_ids, term_slugs = _build_catalogue(module)

    # All valid ids: concept ids + all term slugs mentioned by any concept
    all_term_slugs: set[str] = set()
    for s in term_slugs.values():
        all_term_slugs |= s
    valid_ids = concept_ids | all_term_slugs

    prompt = (
        "Here is the concept catalogue for a learning module. "
        "Emit typed relationships between these concepts.\n\n"
        f"{catalogue}"
    )

    ctx = tracer.start_as_current_span("kg.extract") if tracer else _null_span()
    with ctx:
        try:
            result = llm.generate(prompt, system=_EXTRACT_SYSTEM, tool_schema=_EXTRACT_SCHEMA)
            if not isinstance(result, dict):
                _log.warning("[kg.extractor] Unexpected LLM response type: %s", type(result))
                return []

            raw_edges = _coerce_edges(result.get("edges", []))
            valid: list[dict] = []
            dropped = 0
            for edge in raw_edges:
                src = edge.get("source_id", "")
                dst = edge.get("target_id", "")
                rel = edge.get("relation", "")
                if src not in valid_ids or dst not in valid_ids:
                    dropped += 1
                    continue
                if rel not in _LLM_RELATIONS:
                    dropped += 1
                    continue
                if src == dst:
                    continue
                valid.append(edge)

            if dropped:
                _log.info("[kg.extractor] Dropped %d edges with unknown ids/relations", dropped)
            _log.info("[kg.extractor] Extracted %d valid edges for module %s", len(valid), module.module_id)
            return valid

        except Exception as exc:
            _log.warning("[kg.extractor] LLM extraction failed for %s: %s", module.module_id, exc)
            return []


def build_module_graph(
    module: LearningModule,
    llm,
    store: KnowledgeGraphStore,
    tracer=None,
) -> KnowledgeGraphStore:
    """Orchestrate full KG build: LLM edges → acyclicity → save.

    The store is expected to already have structural edges (PART_OF, FOLLOWS,
    MENTIONS) added by the pipeline. This function adds LLM-inferred edges,
    breaks any PREREQUISITE_OF cycles, and persists to GraphML.
    """
    edges = extract_edges(module, llm, tracer=tracer)

    # Add term nodes and LLM edges
    for edge in edges:
        src = edge["source_id"]
        dst = edge["target_id"]
        rel_str = edge["relation"]
        confidence = float(edge.get("confidence", 1.0))

        # Register TERM nodes on the fly if they are term slugs
        for nid in (src, dst):
            if not store._g.has_node(nid):
                store._g.add_node(nid, node_type="TERM", label=nid)

        try:
            rel = RelationType(rel_str)
        except ValueError:
            continue

        store.add_edge(src, dst, rel, weight=confidence, source="llm")

    # Enforce acyclicity on PREREQUISITE_OF edges
    removed = store.break_prerequisite_cycles()
    if removed:
        _log.info("[kg] Broke %d prerequisite cycle(s) for module %s", removed, module.module_id)

    store.save()
    return store


class _null_span:
    """No-op context manager used when tracer is None."""
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass
