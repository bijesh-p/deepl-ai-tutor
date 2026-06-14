from __future__ import annotations

import re
import uuid
from backend.content.llm_client import LLMClient
from backend.content.models import Diagram, EnrichedTopic

_TOOL_SCHEMA = {
    "name": "return_diagram",
    "description": "Return a Mermaid diagram for the topic.",
    "input_schema": {
        "type": "object",
        "properties": {
            "mermaid_code": {
                "type": "string",
                "description": "Valid Mermaid diagram code showing concept relationships.",
            },
            "caption": {
                "type": "string",
                "description": "Short caption describing the diagram.",
            },
        },
        "required": ["mermaid_code", "caption"],
    },
}

_SYSTEM = (
    "You are an expert at creating clear educational diagrams. "
    "You MUST always generate a Mermaid diagram — a concept map, flowchart, or "
    "sequence diagram that shows how the key ideas in the topic relate to each other. "
    "Use valid Mermaid v10 syntax. "
    "Mermaid syntax rules you must follow: "
    "Never use a double-quote character or a backslash-escaped quote (\\\")"
    " inside a label — Mermaid does not support escaped quotes, and it produces a syntax error. "
    "If a label needs to show quoted text, use the HTML entity #quot; instead, or "
    "rephrase without quotes. "
    "Do not create an edge from a subgraph to itself."
)


def generate_diagrams(
    enriched: EnrichedTopic,
    llm: LLMClient,
) -> list[Diagram]:
    """Generate a Mermaid diagram for a topic if one adds value."""
    prompt = (
        f"Topic: {enriched.topic.title}\n\n"
        f"{enriched.content_md}\n\n"
        "Generate a Mermaid diagram showing how the key ideas in this topic relate."
    )

    result = llm.generate(
        prompt=prompt,
        system=_SYSTEM,
        tool_schema=_TOOL_SCHEMA,
    )

    mermaid_code = result.get("mermaid_code", "").strip()
    if not mermaid_code:
        return []

    return [
        Diagram(
            diagram_id=str(uuid.uuid4()),
            diagram_type="mermaid",
            content=_sanitize_mermaid(mermaid_code),
            caption=result.get("caption", ""),
        )
    ]


def _sanitize_mermaid(code: str) -> str:
    """Fix common LLM mistakes that produce Mermaid syntax errors."""
    code = code.strip()
    # Strip ```mermaid ... ``` or ``` ... ``` fences
    code = re.sub(r"^```(?:mermaid)?\s*\n?", "", code, flags=re.IGNORECASE)
    code = re.sub(r"\n?```\s*$", "", code)
    code = code.strip()
    # Fix escaped quotes — Mermaid does not support \" inside labels
    code = code.replace('\\"', "#quot;")
    return code
