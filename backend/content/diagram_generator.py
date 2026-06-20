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
    "1. Choose diagram direction based on content type: "
    "   - Use 'flowchart LR' (left-to-right) when the content describes a PROCESS or SEQUENCE "
    "     (steps that happen in order, pipelines, workflows). "
    "   - Use 'flowchart TD' (top-down) when the content describes a HIERARCHY or TAXONOMY "
    "     (categories, types, components of something). "
    "   - Default to TD when unsure. "
    "2. HARD LIMIT: Maximum 6 nodes total including the root. Count carefully before outputting. "
    "   If you have more than 6 concepts, merge the least important ones into a single grouped "
    "   node labelled 'Other Concepts'. Every node label must be 1-4 words — no full sentences. "
    "3. Do NOT use subgraphs. Keep the diagram flat. "
    "4. Never use a double-quote character or backslash-escaped quote inside a label — "
    "use #quot; if needed, or rephrase without quotes. "
    "5. Output only the Mermaid code with no markdown fences around it. "
    "6. ONLY use concepts and terms that appear explicitly in the provided source text. "
    "Do NOT invent nodes, do NOT include meta-concepts like 'quiz', 'questions', 'diagnostic', "
    "'learning', or 'slide'. Show only the subject-matter relationships from the text itself. "
    "Do NOT create nodes for concepts that describe problems, misconceptions, hype, criticism, "
    "or warnings about AI (e.g. 'snake oil', 'hype', 'limitations', 'risks', 'bias'). "
    "These are narrative concepts, not structural ones. Only diagram what a technology IS and "
    "HOW it works, not what it is NOT or why it fails. "
    "Exception: if excluding evaluative concepts would leave fewer than 3 nodes, you MAY include "
    "the most neutral/factual framing of those concepts as plain descriptive labels. "
    "For example, instead of 'AI Snake Oil' use 'AI Limitations', instead of 'Hype' use "
    "'Realistic Expectations'. Reframe negatives as neutral descriptors. "
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
    "    class NodeD outcome\n"
    "9. Choose the root node as the single most central TECHNICAL concept in the source text — "
    "not the topic title. For example, if the topic is 'Data-Driven vs Rule-Based AI', the root "
    "should be 'AI Approaches', not 'Artificial Intelligence'. Keep the root abstract and the "
    "children concrete. "
    "10. No single node should have more than 4 direct children. If a concept has 5+ children, "
    "group them under an intermediate node. For example, instead of AI → A, B, C, D, E, F "
    "use AI → Group1 → A, B, C and AI → Group2 → D, E, F. "
    "11. Keep the diagram shallow — maximum 3 levels of depth (root → children → grandchildren). "
    "Do not create 4+ level hierarchies as they become too tall to display. If content is complex, "
    "use grouping nodes instead of adding more levels."
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
    base_prompt = (
        f"Topic: {topic.title}\n"
        f"Summary: {topic.summary}\n\n"
        f"Source text:\n{source_text[:3000]}\n\n"
        "Generate a Mermaid diagram showing how the key concepts in this source text relate to each other. "
        "Use ONLY terms and concepts that appear in the source text above. "
        "Do not add anything that is not mentioned in the text.\n\n"
        "Also write a single sentence for the caption field that describes what the diagram shows "
        "(e.g. 'How supervised learning maps inputs to outputs via a trained model')."
    )

    def _attempt(prompt: str) -> tuple[str, str]:
        result = llm.generate(prompt=prompt, system=_DIAGRAM_SYSTEM, tool_schema=_DIAGRAM_TOOL_SCHEMA)
        if not isinstance(result, dict):
            return "", ""
        return _sanitize_mermaid(result.get("mermaid_code", "").strip()), result.get("caption", "")

    def _node_count(code: str) -> int:
        return len(set(re.findall(r'\b([A-Za-z][A-Za-z0-9_]*)\s*[\[\({]', code)))

    def _has_edge(code: str) -> bool:
        return "-->" in code or "---" in code

    try:
        sanitized, caption = _attempt(base_prompt)

        # If thin diagram (< 3 nodes), retry with an enrichment nudge
        if sanitized and _has_edge(sanitized) and _node_count(sanitized) < 3:
            retry_prompt = (
                base_prompt
                + "\n\nThe previous diagram had too few nodes. "
                "Add 2-3 more concrete sub-concepts from the source text to make the diagram richer."
            )
            retry_sanitized, retry_caption = _attempt(retry_prompt)
            if retry_sanitized and _has_edge(retry_sanitized) and _node_count(retry_sanitized) >= _node_count(sanitized):
                sanitized, caption = retry_sanitized, retry_caption

        # Hard reject: no edges or fewer than 2 nodes
        if not sanitized or not _has_edge(sanitized) or _node_count(sanitized) < 2:
            return None

        return Diagram(
            diagram_id=str(uuid.uuid4()),
            diagram_type="mermaid",
            content=sanitized,
            caption=caption,
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

    # Strip click event lines — not supported by st_mermaid
    code = re.sub(r'^[ \t]*click\s+\S.*$', '', code, flags=re.MULTILINE)

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

    # Hard node cap: reject diagrams with more than 7 nodes
    node_pattern = re.compile(r'^\s*(\w+)\s*[\[\({]', re.MULTILINE)
    capped_node_ids = list(dict.fromkeys(m.group(1) for m in node_pattern.finditer(code)))
    if len(capped_node_ids) > 7:
        return ""

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
