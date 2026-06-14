from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from backend.content.models import Diagram, EnrichedTopic, Topic

# ---------------------------------------------------------------------------
# SlideAnchor — the visual/structural foundation generated BEFORE any text
# ---------------------------------------------------------------------------

@dataclass
class SlideAnchor:
    """Holds either a Mermaid diagram or a bullet list — never both, never empty."""
    diagram: Diagram | None        # set when diagram generation succeeded
    bullets: list[str]             # set when diagram failed; 4-6 key points

    @property
    def has_diagram(self) -> bool:
        return self.diagram is not None

    def bullets_md(self) -> str:
        return "\n".join(f"- {b}" for b in self.bullets)


# ---------------------------------------------------------------------------
# Diagram tool schema
# ---------------------------------------------------------------------------

_DIAGRAM_TOOL_SCHEMA = {
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

_DIAGRAM_SYSTEM = (
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

# ---------------------------------------------------------------------------
# Bullet fallback tool schema
# ---------------------------------------------------------------------------

_BULLETS_TOOL_SCHEMA = {
    "name": "return_key_bullets",
    "description": "Return 4-6 key bullet points summarising the most important ideas in this topic.",
    "input_schema": {
        "type": "object",
        "properties": {
            "bullets": {
                "type": "array",
                "minItems": 4,
                "maxItems": 6,
                "items": {"type": "string"},
                "description": "Each bullet is one concise key idea (1-2 sentences max).",
            }
        },
        "required": ["bullets"],
    },
}

_BULLETS_SYSTEM = (
    "You are an expert educator. Extract the 4-6 most important ideas from the text. "
    "Each bullet must be self-contained and concise. No fluff, no repetition."
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_slide_anchor(source_text: str, topic: Topic, llm) -> SlideAnchor:
    """Generate the slide anchor from source text and topic metadata.

    Tries a Mermaid diagram first. Falls back to key bullets if diagram
    is empty, invalid, or the LLM call fails.
    """
    diagram = _try_diagram(source_text, topic, llm)
    if diagram is not None:
        return SlideAnchor(diagram=diagram, bullets=[])

    bullets = _try_bullets(source_text, topic, llm)
    return SlideAnchor(diagram=None, bullets=bullets)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _try_diagram(source_text: str, topic: Topic, llm) -> Diagram | None:
    prompt = (
        f"Topic: {topic.title}\n"
        f"Summary: {topic.summary}\n\n"
        f"Source text:\n{source_text[:3000]}\n\n"
        "Generate a Mermaid diagram showing how the key ideas in this topic relate."
    )
    try:
        result = llm.generate(
            prompt=prompt,
            system=_DIAGRAM_SYSTEM,
            tool_schema=_DIAGRAM_TOOL_SCHEMA,
        )
        if not isinstance(result, dict):
            return None
        mermaid_code = result.get("mermaid_code", "").strip()
        if not mermaid_code:
            return None
        return Diagram(
            diagram_id=str(uuid.uuid4()),
            diagram_type="mermaid",
            content=_sanitize_mermaid(mermaid_code),
            caption=result.get("caption", ""),
        )
    except Exception:
        return None


def _try_bullets(source_text: str, topic: Topic, llm) -> list[str]:
    prompt = (
        f"Topic: {topic.title}\n"
        f"Summary: {topic.summary}\n\n"
        f"Source text:\n{source_text[:3000]}\n\n"
        "Extract the 4-6 most important key ideas."
    )
    try:
        result = llm.generate(
            prompt=prompt,
            system=_BULLETS_SYSTEM,
            tool_schema=_BULLETS_TOOL_SCHEMA,
        )
        if isinstance(result, dict):
            bullets = result.get("bullets", [])
            if bullets:
                return bullets
    except Exception:
        pass
    # Hard fallback — use the topic summary as a single bullet
    return [topic.summary] if topic.summary else ["Key ideas from this section."]


def _sanitize_mermaid(code: str) -> str:
    code = code.strip()
    code = re.sub(r"^```(?:mermaid)?\s*\n?", "", code, flags=re.IGNORECASE)
    code = re.sub(r"\n?```\s*$", "", code)
    code = code.strip()
    code = code.replace('\\"', "#quot;")
    return code


# ---------------------------------------------------------------------------
# Legacy: generate_diagrams(enriched, llm) — kept for any callers outside pipeline
# ---------------------------------------------------------------------------

def generate_diagrams(enriched: EnrichedTopic, llm) -> list[Diagram]:
    """Legacy wrapper — generate a diagram from an already-enriched topic."""
    anchor = generate_slide_anchor(enriched.content_md, enriched.topic, llm)
    if anchor.has_diagram:
        return [anchor.diagram]
    return []
