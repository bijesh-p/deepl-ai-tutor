"""NetworkX-backed per-module knowledge graph with GraphML persistence.

Each module gets its own KnowledgeGraphStore. The store is populated during
content generation (structural edges) and after extraction (LLM edges), then
persisted to data/graph/{module_id}.graphml.

Retrieval helpers (prerequisites, related, neighborhood, teaching_order) are
used by retrieval.py to select which concepts to fetch from ChromaDB.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import networkx as nx

from backend.content.knowledge_graph.ontology import NodeType, RelationType, slug

_log = logging.getLogger(__name__)

_DEFAULT_GRAPH_DIR = "data/graph"


def _graph_dir() -> Path:
    d = Path(os.environ.get("AI_TUTOR_GRAPH_DIR", _DEFAULT_GRAPH_DIR))
    d.mkdir(parents=True, exist_ok=True)
    return d


class KnowledgeGraphStore:
    """In-memory MultiDiGraph with GraphML load/save and traversal helpers."""

    def __init__(self, module_id: str) -> None:
        self.module_id = module_id
        self._g: nx.MultiDiGraph = nx.MultiDiGraph()

    # ------------------------------------------------------------------
    # Node registration
    # ------------------------------------------------------------------

    def add_module(self, title: str) -> None:
        self._g.add_node(
            self.module_id,
            node_type=NodeType.MODULE.value,
            title=title,
        )

    def add_concept(self, topic_id: str, title: str, summary: str, order: int) -> None:
        self._g.add_node(
            topic_id,
            node_type=NodeType.CONCEPT.value,
            title=title,
            summary=summary,
            order=order,
        )

    def add_term(self, label: str) -> str:
        """Register a TERM node and return its slug node_id."""
        node_id = slug(label)
        if not self._g.has_node(node_id):
            self._g.add_node(node_id, node_type=NodeType.TERM.value, label=label)
        return node_id

    # ------------------------------------------------------------------
    # Edge registration (idempotent by key)
    # ------------------------------------------------------------------

    def add_edge(
        self,
        src: str,
        dst: str,
        relation: RelationType,
        weight: float = 1.0,
        source: str = "llm",
    ) -> None:
        """Add a directed edge; silently skip if the exact (src, dst, relation) exists."""
        rel_val = relation.value
        for _, _, data in self._g.edges(src, data=True):
            if data.get("relation") == rel_val and _ == dst:
                return
        # Check all existing edges between src and dst
        if self._g.has_edge(src, dst):
            for key in self._g[src][dst]:
                if self._g[src][dst][key].get("relation") == rel_val:
                    return
        self._g.add_edge(src, dst, relation=rel_val, weight=weight, source=source)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> Path:
        path = _graph_dir() / f"{self.module_id}.graphml"
        nx.write_graphml(self._g, str(path))
        _log.info("[kg] Saved graph for %s → %s (%d nodes, %d edges)",
                  self.module_id, path, self._g.number_of_nodes(), self._g.number_of_edges())
        return path

    @classmethod
    def load(cls, module_id: str) -> Optional["KnowledgeGraphStore"]:
        path = _graph_dir() / f"{module_id}.graphml"
        if not path.exists():
            return None
        try:
            store = cls(module_id)
            store._g = nx.read_graphml(str(path))
            return store
        except Exception as exc:
            _log.warning("[kg] Failed to load graph for %s: %s", module_id, exc)
            return None

    # ------------------------------------------------------------------
    # Cycle breaking (PREREQUISITE_OF only)
    # ------------------------------------------------------------------

    def break_prerequisite_cycles(self) -> int:
        """Remove lowest-weight PREREQUISITE_OF edge in each detected cycle.

        Returns the number of edges removed.
        """
        prereq_view = nx.MultiDiGraph()
        for u, v, data in self._g.edges(data=True):
            if data.get("relation") == RelationType.PREREQUISITE_OF.value:
                prereq_view.add_edge(u, v, weight=data.get("weight", 1.0), _uv=(u, v))

        removed = 0
        try:
            cycles = list(nx.simple_cycles(prereq_view))
        except Exception:
            return 0

        for cycle in cycles:
            # Find the edge in the cycle with the lowest weight
            min_weight = float("inf")
            min_edge: tuple | None = None
            for i, node in enumerate(cycle):
                nxt = cycle[(i + 1) % len(cycle)]
                if prereq_view.has_edge(node, nxt):
                    for key in prereq_view[node][nxt]:
                        w = prereq_view[node][nxt][key].get("weight", 1.0)
                        if w < min_weight:
                            min_weight = w
                            min_edge = (node, nxt)

            if min_edge and self._g.has_edge(*min_edge):
                rel = RelationType.PREREQUISITE_OF.value
                keys_to_remove = [
                    k for k, d in self._g[min_edge[0]][min_edge[1]].items()
                    if d.get("relation") == rel
                ]
                for k in keys_to_remove:
                    self._g.remove_edge(min_edge[0], min_edge[1], key=k)
                    prereq_view.remove_edge(*min_edge)
                    removed += 1
                    _log.info("[kg] Broke cycle: removed %s --PREREQUISITE_OF--> %s (weight=%.2f)",
                              *min_edge, min_weight)

        return removed

    # ------------------------------------------------------------------
    # Traversal helpers
    # ------------------------------------------------------------------

    def _concept_ids(self) -> set[str]:
        return {
            n for n, d in self._g.nodes(data=True)
            if d.get("node_type") == NodeType.CONCEPT.value
        }

    def prerequisites(self, topic_id: str, depth: int = 1) -> list[str]:
        """Return concept ids that are prerequisites of topic_id up to given depth.

        Follows PREREQUISITE_OF edges in reverse: A --PREREQ_OF--> B means
        A must be learned before B, so B's prerequisites are nodes with edges
        pointing TO B.
        """
        result: list[str] = []
        visited: set[str] = {topic_id}
        frontier = {topic_id}

        for _ in range(depth):
            next_frontier: set[str] = set()
            for node in frontier:
                for pred in self._g.predecessors(node):
                    if pred in visited:
                        continue
                    for key in self._g[pred][node]:
                        if self._g[pred][node][key].get("relation") == RelationType.PREREQUISITE_OF.value:
                            if pred in self._concept_ids():
                                next_frontier.add(pred)
                            break
            result.extend(next_frontier - visited)
            visited |= next_frontier
            frontier = next_frontier

        return result

    def related(self, topic_id: str, k: int = 3) -> list[str]:
        """Return up to k concept ids related to topic_id via RELATED_TO edges (bidirectional)."""
        concepts = self._concept_ids()
        result: set[str] = set()

        for _, v, data in self._g.edges(topic_id, data=True):
            if data.get("relation") == RelationType.RELATED_TO.value and v in concepts:
                result.add(v)
        for u, _, data in self._g.in_edges(topic_id, data=True):
            if data.get("relation") == RelationType.RELATED_TO.value and u in concepts:
                result.add(u)

        result.discard(topic_id)
        return list(result)[:k]

    def neighborhood(self, topic_id: str, depth: int = 1) -> list[str]:
        """Return concept ids within depth hops of topic_id (any relation)."""
        concepts = self._concept_ids()
        visited: set[str] = {topic_id}
        frontier = {topic_id}

        for _ in range(depth):
            next_frontier: set[str] = set()
            for node in frontier:
                for nbr in list(self._g.successors(node)) + list(self._g.predecessors(node)):
                    if nbr not in visited and nbr in concepts:
                        next_frontier.add(nbr)
            visited |= next_frontier
            frontier = next_frontier

        visited.discard(topic_id)
        return list(visited)

    def teaching_order(self) -> list[str]:
        """Return concept ids in topological order respecting PREREQUISITE_OF edges.

        Falls back to FOLLOWS order when no prerequisite edges exist. Concepts
        not reachable via either are appended in arbitrary order.
        """
        concepts = self._concept_ids()
        prereq_graph = nx.DiGraph()
        prereq_graph.add_nodes_from(concepts)

        for u, v, data in self._g.edges(data=True):
            if (
                data.get("relation") == RelationType.PREREQUISITE_OF.value
                and u in concepts
                and v in concepts
            ):
                prereq_graph.add_edge(u, v)

        try:
            topo = list(nx.topological_sort(prereq_graph))
            # topological_sort puts nodes with no successors last; for teaching
            # we want prerequisites first so reverse the meaning: a node with
            # no prerequisites (in-degree 0) should come first. nx.topological_sort
            # already gives this for a DAG — keep as-is.
            return [n for n in topo if n in concepts]
        except nx.NetworkXUnfeasible:
            pass

        # Fallback: sort by FOLLOWS order attribute
        order_map: dict[str, int] = {}
        for n, d in self._g.nodes(data=True):
            if n in concepts:
                try:
                    order_map[n] = int(d.get("order", 9999))
                except (TypeError, ValueError):
                    order_map[n] = 9999

        return sorted(concepts, key=lambda n: order_map.get(n, 9999))

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return self._g.number_of_nodes()

    def node_count(self) -> int:
        return self._g.number_of_nodes()

    def edge_count(self) -> int:
        return self._g.number_of_edges()
