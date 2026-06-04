from __future__ import annotations

from content.llm_client import LLMClient
from content.models import EnrichedTopic, Topic
from ingestion.models import Document

_TOOL_SCHEMA = {
    "name": "return_enriched_topic",
    "description": "Return enriched learning content for a single topic.",
    "input_schema": {
        "type": "object",
        "properties": {
            "content_md": {
                "type": "string",
                "description": "Learner-friendly explanation in Markdown.",
            },
            "key_takeaways": {
                "type": "array",
                "items": {"type": "string"},
                "description": "3-5 concise bullet-point takeaways.",
            },
        },
        "required": ["content_md", "key_takeaways"],
    },
}

_SYSTEM = (
    "You are an expert educator. "
    "Rewrite the provided topic content into clear, engaging prose for a learner. "
    "Add helpful analogies and highlight important definitions. "
    "Preserve all factual content — do not add new information."
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
        diagrams=[],
        inline_questions=[],
    )
