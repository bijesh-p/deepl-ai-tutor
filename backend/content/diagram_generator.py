from __future__ import annotations

import uuid
from backend.content.llm_client import LLMClient
from backend.content.models import Diagram, EnrichedTopic

_TOOL_SCHEMA = {
    "name": "return_diagram",
    "description": "Return a Mermaid diagram for the topic, or indicate none is needed.",
    "input_schema": {
        "type": "object",
        "properties": {
            "needs_diagram": {
                "type": "boolean",
                "description": "True if a diagram would meaningfully aid understanding.",
            },
            "mermaid_code": {
                "type": "string",
                "description": "Valid Mermaid diagram code (empty string if needs_diagram is false).",
            },
            "caption": {
                "type": "string",
                "description": "Short caption describing the diagram.",
            },
        },
        "required": ["needs_diagram", "mermaid_code", "caption"],
    },
}

_SYSTEM = (
    "You are an expert at creating clear educational diagrams. "
    "Decide if a Mermaid diagram (flowchart, sequence, class, etc.) would meaningfully "
    "aid understanding of the topic. If yes, generate valid Mermaid syntax for Mermaid v10. "
    "If a diagram would not add value, set needs_diagram to false. "
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
        "Should a diagram be generated for this topic? If yes, produce Mermaid code."
    )

    result = llm.generate(
        prompt=prompt,
        system=_SYSTEM,
        tool_schema=_TOOL_SCHEMA,
    )

    if not result.get("needs_diagram") or not result.get("mermaid_code", "").strip():
        return []

    return [
        Diagram(
            diagram_id=str(uuid.uuid4()),
            diagram_type="mermaid",
            content=_sanitize_mermaid(result["mermaid_code"]),
            caption=result.get("caption", ""),
        )
    ]


def _sanitize_mermaid(code: str) -> str:
    """Fix common LLM mistakes that produce Mermaid syntax errors."""
    return code.replace('\\"', "#quot;")
