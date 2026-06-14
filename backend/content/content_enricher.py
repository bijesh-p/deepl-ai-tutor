from __future__ import annotations

from backend.core.llm_client import BaseLLMClient as LLMClient
from backend.content.models import EnrichedTopic, Topic

_TOOL_SCHEMA = {
    "name": "return_enriched_topic",
    "description": "Return enriched learning content for a single topic.",
    "input_schema": {
        "type": "object",
        "properties": {
            "top_concepts": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 2,
                "maxItems": 3,
                "description": "The 2-3 most important concepts from this topic, each as a short phrase.",
            },
            "content_md": {
                "type": "string",
                "description": (
                    "Conversational explanation in Markdown. Write as if talking to "
                    "a curious student — use 'you', 'let\\'s', 'think of it like...'. "
                    "The explanation must be grounded in the slide anchor provided "
                    "(diagram or bullet points). Walk through each element of the anchor. "
                    "Do not introduce concepts not shown in the anchor."
                ),
            },
            "key_takeaways": {
                "type": "array",
                "items": {"type": "string"},
                "description": "3-5 concise bullet-point takeaways.",
            },
        },
        "required": ["top_concepts", "content_md", "key_takeaways"],
    },
}

_SYSTEM_WITH_DIAGRAM = (
    "You are a friendly tutor explaining concepts to a curious student. "
    "A slide diagram has already been created for this topic — your job is to write "
    "the spoken explanation that walks through it. "
    "Start by referencing the diagram ('Let\\'s look at this diagram...'), then explain "
    "each node or relationship in plain language with analogies and real-world examples. "
    "Only discuss concepts that appear in the diagram. "
    "Keep it conversational and engaging, not textbook-dry."
)

_SYSTEM_WITH_BULLETS = (
    "You are a friendly tutor explaining concepts to a curious student. "
    "A set of key bullet points has been prepared for this topic — your job is to write "
    "the spoken explanation that expands on each one. "
    "Start by referencing the bullets ('Here are the key ideas for this topic...'), then "
    "explain each bullet in plain language with analogies and real-world examples. "
    "Only discuss concepts listed in the bullet points. "
    "Keep it conversational and engaging, not textbook-dry."
)


def enrich(
    topic: Topic,
    source_text: str,
    llm: LLMClient,
    anchor=None,            # SlideAnchor | None  (None = legacy path, no anchor context)
    cached_blocks: list[dict] | None = None,
) -> EnrichedTopic:
    """Write a learner-friendly explanation grounded in the slide anchor.

    If an anchor is provided (diagram or bullets), the explanation walks through
    the anchor and must not stray beyond it. If no anchor is provided (legacy
    callers), falls back to free-form enrichment from source text.
    """
    # Build anchor context block for the prompt
    anchor_block = _anchor_context(anchor)

    prompt = (
        f"Topic: {topic.title}\n"
        f"Summary: {topic.summary}\n\n"
        f"{anchor_block}"
        "Write a conversational explanation for a student based on the anchor above."
    )

    if anchor is not None:
        system = _SYSTEM_WITH_DIAGRAM if anchor.has_diagram else _SYSTEM_WITH_BULLETS
    else:
        system = (
            "You are a friendly tutor explaining concepts in a conversation. "
            "Write as if talking to a curious student — use analogies and real-world examples. "
            "Keep it engaging and conversational, not textbook-dry. "
            "Preserve all factual content — do not invent new information."
        )

    result = llm.generate(
        prompt=prompt,
        system=system,
        tool_schema=_TOOL_SCHEMA,
        cached_blocks=cached_blocks,
    )

    return EnrichedTopic(
        topic=topic,
        content_md=result["content_md"],
        key_takeaways=result["key_takeaways"],
        top_concepts=result.get("top_concepts", []),
        diagrams=[],
        inline_questions=[],
    )


def _anchor_context(anchor) -> str:
    """Format the slide anchor as a prompt context block."""
    if anchor is None:
        return ""
    if anchor.has_diagram:
        d = anchor.diagram
        return (
            f"SLIDE DIAGRAM (explain this — do not go beyond it):\n"
            f"Caption: {d.caption}\n"
            f"Mermaid code:\n{d.content}\n\n"
        )
    if anchor.bullets:
        bullet_text = "\n".join(f"- {b}" for b in anchor.bullets)
        return (
            f"SLIDE KEY POINTS (expand on these — do not go beyond them):\n"
            f"{bullet_text}\n\n"
        )
    return ""
