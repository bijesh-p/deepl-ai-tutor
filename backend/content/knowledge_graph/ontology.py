"""Ontology for the per-module knowledge graph.

Defines node types, edge (relation) types, and a stable slug helper for TERM
node identifiers.
"""
from __future__ import annotations

import re
from enum import Enum


class NodeType(Enum):
    MODULE = "MODULE"
    CONCEPT = "CONCEPT"
    TERM = "TERM"


class RelationType(Enum):
    PART_OF = "PART_OF"           # CONCEPT --PART_OF--> MODULE (structural)
    FOLLOWS = "FOLLOWS"           # CONCEPT_n --FOLLOWS--> CONCEPT_{n-1} (structural)
    PREREQUISITE_OF = "PREREQUISITE_OF"   # learn A before B (LLM)
    RELATED_TO = "RELATED_TO"     # symmetric semantic link (LLM)
    ELABORATES = "ELABORATES"     # A is deeper/specialised view of B (LLM)
    MENTIONS = "MENTIONS"         # CONCEPT --MENTIONS--> TERM (structural + LLM)
    DEFINES = "DEFINES"           # CONCEPT is canonical definition of TERM (LLM)


def slug(label: str) -> str:
    """Return a stable, URL-safe id for a TERM node label.

    Lower-cases, strips non-alphanumeric characters, and collapses runs of
    underscores so the same surface form always maps to the same node_id.
    """
    s = label.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = s.strip("_")
    return s or "term"
