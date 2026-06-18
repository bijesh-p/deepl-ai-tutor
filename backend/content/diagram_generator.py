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
    "You are an expert at creating clear, colorful educational diagrams. "
    "Follow ALL rules — no exceptions:\n"
    "1. Choose the best Mermaid flowchart direction for the content: "
    "   - Use 'LR' (left-to-right) ONLY for simple 3-5 node linear flows or pipelines. "
    "   - Use 'TD' (top-down) for hierarchies, taxonomies, branching, or anything with 5+ nodes. "
    "2. Use AT MOST 6 nodes total — this is a hard limit, do not exceed it. "
    "   If the topic has many ideas, pick only the 3-6 most important ones. "
    "   Every node label must be 1-4 words — no full sentences. "
    "3. Do NOT use subgraphs. Keep the diagram flat. "
    "4. Never use a double-quote character or backslash-escaped quote inside a label — "
    "use #quot; if needed, or rephrase without quotes. "
    "5. Output only the Mermaid code with no markdown fences around it. "
    "6. ONLY use concepts and terms that appear explicitly in the provided source text. "
    "Do NOT invent nodes, do NOT include meta-concepts like 'quiz', 'questions', 'diagnostic', "
    "'learning', or 'slide'. Show only the subject-matter relationships from the text itself. "
    "7. Each arrow must represent a real logical relationship (e.g. leads-to, is-a, enables, "
    "consists-of) — not a random connection between terms. "
    "8. Add color using classDef. Classify every node as one of: primary (main concept), "
    "secondary (supporting idea), or outcome (result/application). "
    "Then assign classes and define them like this example at the END of the diagram:\n"
    "    classDef primary fill:#4C9BE8,stroke:#1a5fa8,color:#fff\n"
    "    classDef secondary fill:#F0A500,stroke:#b87800,color:#fff\n"
    "    classDef outcome fill:#2ECC71,stroke:#1a7a43,color:#fff\n"
    "    class NodeA primary\n"
    "    class NodeB,NodeC secondary\n"
    "    class NodeD outcome"
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
        "Generate a Mermaid diagram showing how the key concepts in this source text relate to each other. "
        "Use ONLY terms and concepts that appear in the source text above. "
        "Do not add anything that is not mentioned in the text."
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
        sanitized = _sanitize_mermaid(mermaid_code)
        # Reject if there are no edges — it's not a real diagram
        if "-->" not in sanitized and "---" not in sanitized:
            return None
        # Reject if fewer than 2 nodes — nothing useful to show
        node_count = len(set(re.findall(r'\b([A-Za-z][A-Za-z0-9_]*)\s*[\[\({]', sanitized)))
        if node_count < 2:
            return None
        return Diagram(
            diagram_id=str(uuid.uuid4()),
            diagram_type="mermaid",
            content=sanitized,
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


_DIAGRAM_HEADER_RE = re.compile(
    r'^(flowchart|graph|sequenceDiagram|classDiagram|stateDiagram|erDiagram|gantt|pie)',
    re.IGNORECASE | re.MULTILINE,
)


def _sanitize_mermaid(code: str) -> str:
    code = code.strip()

    # Strip markdown fences
    code = re.sub(r"^```(?:mermaid)?\s*\n?", "", code, flags=re.IGNORECASE)
    code = re.sub(r"\n?```\s*$", "", code)
    code = code.strip()

    # Strip YAML frontmatter (---\n...\n---)
    code = re.sub(r"^---\n.*?\n---\n?", "", code, flags=re.DOTALL)
    code = code.strip()

    # Fix escaped quotes
    code = code.replace('\\"', "#quot;")

    # Replace backticks with single quotes — backticks inside labels break the JS parser
    code = code.replace('`', "'")

    # Replace & with 'and' in node labels to avoid Mermaid parse errors
    code = re.sub(r'\[([^\]]*?)&([^\]]*?)\]', lambda m: f'[{m.group(1)}and{m.group(2)}]', code)
    code = re.sub(r'\(([^\)]*?)&([^\)]*?)\)', lambda m: f'({m.group(1)}and{m.group(2)})', code)

    # Replace () inside [] node labels with {} to prevent parse errors
    # e.g. A[Feature Extraction (CNN)] → A[Feature Extraction {CNN}]
    # Skips shape markers like [(text)] where ( immediately follows [
    code = re.sub(
        r'\[([A-Za-z0-9][^\]]*?)\(([^\)]*?)\)([^\]]*?)\]',
        lambda m: f'[{m.group(1)}{{{m.group(2)}}}{m.group(3)}]',
        code,
    )

    # Strip subgraph wrappers — keep inner node lines, remove the subgraph/end lines
    code = re.sub(r'^[ \t]*subgraph\b[^\n]*\n?', '', code, flags=re.MULTILINE)
    code = re.sub(r'^[ \t]*end\s*$', '', code, flags=re.MULTILINE)

    # Strip edge labels (-->|label| → -->) which often cause parse failures
    code = re.sub(r'-->\s*\|[^|]*\|', '-->', code)
    code = re.sub(r'---\s*\|[^|]*\|', '---', code)

    # Split pipe-separated classDef lines into individual lines
    # e.g. "classDef primary fill:#aaa | secondary fill:#bbb" → two separate lines
    def _split_classdef(m):
        parts = [p.strip() for p in m.group(1).split('|')]
        return '\n'.join(f'classDef {p}' for p in parts if p)
    code = re.sub(r'classDef\s+(.+)', _split_classdef, code)

    # Auto-prepend "flowchart TD" if no valid diagram type header present
    if not _DIAGRAM_HEADER_RE.search(code):
        code = "flowchart TD\n" + code

    # Count distinct node IDs
    node_ids = list(dict.fromkeys(re.findall(r'\b([A-Za-z][A-Za-z0-9_]*)\s*[\[\({]', code)))
    node_ids += [n for n in re.findall(r'(?:-->|---)\s*([A-Za-z][A-Za-z0-9_]*)\b', code)
                 if n not in node_ids]
    node_ids = list(dict.fromkeys(node_ids))

    # Switch LR → TD when too many nodes
    if len(node_ids) > 5:
        code = re.sub(r'^(flowchart|graph)\s+LR', r'\1 TD', code, count=1, flags=re.MULTILINE)

    # Auto-assign classDef colors if definitions exist but assignments are missing
    has_classdef = "classDef" in code
    has_class_assign = bool(re.search(r'^[ \t]*class\s+\w', code, re.MULTILINE))
    if has_classdef and not has_class_assign and node_ids:
        classes = ["primary", "secondary", "outcome"]
        assignments = [f"class {nid} {classes[i % len(classes)]}" for i, nid in enumerate(node_ids)]
        code = code + "\n" + "\n".join(assignments)

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
