from __future__ import annotations

from backend.content.llm_client import LLMClient
from backend.content.models import EnrichedTopic, Topic
from backend.ingestion.models import Document

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
                    "a curious student — use 'you', 'let's', 'think of it like...'. "
                    "Use analogies and real-world examples. Keep it engaging, not textbook-dry."
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

_SYSTEM = (
    "You are a friendly tutor explaining concepts in a conversation. "
    "Write as if you are talking to a curious student — use 'you', 'let us explore', "
    "'think of it like...'. Start by identifying the 2-3 top concepts, then explain "
    "each one with analogies and real-world examples. "
    "Keep it engaging and conversational, not textbook-dry. "
    "Preserve all factual content — do not invent new information."
)


def enrich(
    topic: Topic,
    source_text: str,
    llm: LLMClient,
    cached_blocks: list[dict] | None = None,
) -> EnrichedTopic:
    """Rewrite topic content into learner-friendly Markdown."""
    prompt = (
        f"Topic: {topic.title}\n"
        f"Summary: {topic.summary}\n\n"
        "Enrich the above topic using the source document content provided."
    )

    result = llm.generate(
        prompt=prompt,
        system=_SYSTEM,
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
