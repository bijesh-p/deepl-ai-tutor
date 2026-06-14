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
    "You are an expert at creating clear educational slide diagrams. "
    "Follow ALL rules — no exceptions:\n"
    "1. Always generate a Mermaid flowchart (direction LR). "
    "2. Use at most 6 nodes total. Every node label must be 1-4 words — no full sentences. "
    "3. Do NOT use subgraphs. Keep the diagram flat. "
    "4. Never use a double-quote character or backslash-escaped quote inside a label — "
    "use #quot; if needed, or rephrase without quotes. "
    "5. Do not create an edge from a subgraph to itself. "
    "6. Output only the Mermaid code with no markdown fences around it."
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
