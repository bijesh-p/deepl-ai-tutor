from __future__ import annotations

from content.llm_client import LLMClient
from content.models import EnrichedTopic, Topic
from ingestion.models import Document

_SYSTEM = (
    "You are an expert educator who specialises in writing clear, engaging "
    "learning material for university students. "
    "Preserve all factual content from the source — do not invent new facts. "
    "Use plain language, helpful analogies, and concrete examples."
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "content_md": {"type": "string"},
        "key_takeaways": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["content_md", "key_takeaways"],
}


def enrich(topic: Topic, doc: Document, llm: LLMClient) -> EnrichedTopic:
    """Rewrite a Topic's source sections into learner-friendly Markdown content.

    Returns an EnrichedTopic with enriched prose and 3-5 key takeaways.
    Diagrams and inline questions are empty lists — filled by later pipeline steps.
    """
    source_text = _gather_source_text(topic, doc)

    prompt = (
        f"You are writing a learning module section titled: '{topic.title}'\n\n"
        f"Source content:\n{source_text}\n\n"
        "Rewrite this into clear, learner-friendly Markdown. "
        "Use headings, bullet points, bold key terms, and short paragraphs. "
        "Add a helpful analogy or example where appropriate. "
        "Then provide 3-5 concise key takeaways as a list of strings. "
        "Return a JSON object with keys 'content_md' and 'key_takeaways'."
    )

    result: dict = llm.generate(prompt, system=_SYSTEM, response_schema=_SCHEMA)

    return EnrichedTopic(
        topic=topic,
        content_md=result["content_md"],
        key_takeaways=result["key_takeaways"],
        diagrams=[],
        inline_questions=[],
    )


def _gather_source_text(topic: Topic, doc: Document) -> str:
    section_map = {s.section_id: s for s in doc.sections}
    parts = []
    for sid in topic.source_section_ids:
        sec = section_map.get(sid)
        if sec:
            parts.append(f"### {sec.title}\n{sec.body}")
    return "\n\n".join(parts) if parts else topic.summary
