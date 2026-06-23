"""Graph-guided hybrid retrieval.

Combines graph traversal (which concepts to fetch) with ChromaDB definition
lookup (the text of those concepts). Falls back gracefully to pure vector
retrieval when no graph exists for the module.
"""
from __future__ import annotations

import json
import logging

from backend.content.knowledge_graph.store import KnowledgeGraphStore

_log = logging.getLogger(__name__)

_DEFAULT_MAX_DEFS = 3


def graph_guided_context(
    module_id: str,
    topic_id: str | None,
    query_text: str,
    mode: str = "present",
    max_defs: int = _DEFAULT_MAX_DEFS,
) -> str:
    """Return a context string for the tutor, guided by the module's knowledge graph.

    Algorithm:
    1. Load the KnowledgeGraphStore for module_id. If absent → pure vector fallback.
    2. Pick candidate concept ids by mode:
       - "present"  → related(k) ∪ prerequisites(depth=1)
       - "hint"     → prerequisites(depth=1) first, then related
       - "simplify" → prerequisites(depth=2) ordered by teaching_order()
    3. Fetch each candidate's definition from ChromaDB by topic_id filter.
    4. Top up with vector similarity on query_text if graph yields too few.
    5. Return concatenated definitions capped at max_defs (same shape as _retrieve_context).

    Non-fatal: any exception returns "" so a missing/corrupt graph never breaks a session.
    """
    try:
        store = KnowledgeGraphStore.load(module_id)
        if store is None or topic_id is None:
            return _vector_fallback(module_id, query_text, n_results=max_defs)

        # Select candidate ids by mode
        if mode == "simplify":
            prereqs = store.prerequisites(topic_id, depth=2)
            order = store.teaching_order()
            # Sort by teaching order (deepest prerequisite first)
            order_map = {nid: i for i, nid in enumerate(order)}
            candidates = sorted(prereqs, key=lambda n: order_map.get(n, 9999))
        elif mode == "hint":
            prereqs = store.prerequisites(topic_id, depth=1)
            related = store.related(topic_id, k=max_defs)
            # prereqs first (the missing-foundation case)
            seen: set[str] = set()
            candidates = []
            for n in prereqs + related:
                if n not in seen:
                    seen.add(n)
                    candidates.append(n)
        else:  # "present"
            related = store.related(topic_id, k=max_defs)
            prereqs = store.prerequisites(topic_id, depth=1)
            seen = set()
            candidates = []
            for n in related + prereqs:
                if n not in seen:
                    seen.add(n)
                    candidates.append(n)

        candidates = candidates[:max_defs]

        # Fetch definitions from ChromaDB
        defs = _fetch_definitions(module_id, candidates)

        # Top up with vector similarity if graph yields too few
        if len(defs) < max_defs:
            extra = _vector_fallback(module_id, query_text, n_results=max_defs - len(defs))
            if extra:
                defs.append(extra)

        return "\n\n".join(defs) if defs else ""

    except Exception as exc:
        _log.debug("[kg.retrieval] graph_guided_context error (%s): %s — falling back to vector", type(exc).__name__, exc)
        try:
            return _vector_fallback(module_id, query_text, n_results=max_defs)
        except Exception:
            return ""


def _fetch_definitions(module_id: str, topic_ids: list[str]) -> list[str]:
    """Fetch definition text from ChromaDB for each topic_id."""
    if not topic_ids:
        return []

    try:
        from backend.core.mcp_client import get_client

        client = get_client("storage_server")
        results: list[str] = []
        for tid in topic_ids:
            try:
                raw = client.call(
                    "query_vector_db",
                    query_text="",
                    n_results=1,
                    where_filter={"module_id": module_id, "topic_id": tid},
                )
                docs = json.loads(raw).get("documents", [])
                if docs and docs[0]:
                    results.append(docs[0][0])
            except Exception:
                continue
        return results
    except Exception as exc:
        _log.debug("[kg.retrieval] _fetch_definitions error: %s", exc)
        return []


def _vector_fallback(module_id: str, query_text: str, n_results: int = 2) -> str:
    """Pure vector similarity retrieval — same as the legacy _retrieve_context."""
    try:
        from backend.core.mcp_client import get_client

        raw = get_client("storage_server").call(
            "query_vector_db",
            query_text=query_text,
            n_results=n_results,
            where_filter={"module_id": module_id},
        )
        documents = json.loads(raw).get("documents", [])
        if documents and documents[0]:
            return "\n\n".join(documents[0])
    except Exception:
        pass
    return ""
