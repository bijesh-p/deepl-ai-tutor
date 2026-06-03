from __future__ import annotations

import uuid

from content.llm_client import LLMClient
from content.models import Topic
from ingestion.models import Document

_SYSTEM = (
    "You are an expert instructional designer. "
    "Your job is to analyse educational content and organise it into clear, "
    "focused learning topics suitable for self-study."
)

_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "source_section_ids": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["title", "summary", "source_section_ids"],
    },
}


def decompose(doc: Document, llm: LLMClient) -> list[Topic]:
    """Break a Document into an ordered list of learning Topics using the LLM.

    Each Topic groups one or more related sections into a single focused concept.
    The LLM receives all section titles and bodies and returns a structured JSON
    list that is mapped onto Topic dataclasses.
    """
    sections_text = "\n\n".join(
        f"[section_id: {s.section_id}]\nTitle: {s.title}\n{s.body}"
        for s in doc.sections
    )

    prompt = (
        f"The following document is titled '{doc.title}'. "
        "It has been split into sections listed below.\n\n"
        f"{sections_text}\n\n"
        "Group these sections into 3-8 focused learning topics. "
        "Each topic should cover one clear concept. "
        "A topic may reference multiple section_ids if they belong together. "
        "Return a JSON array where each element has: "
        "'title' (string), 'summary' (one sentence), "
        "'source_section_ids' (array of section_id strings from above)."
    )

    raw: list[dict] = llm.generate(prompt, system=_SYSTEM, response_schema=_SCHEMA)

    topics: list[Topic] = []
    for order, item in enumerate(raw, start=1):
        topics.append(
            Topic(
                topic_id=str(uuid.uuid4()),
                title=item["title"],
                summary=item["summary"],
                source_section_ids=item["source_section_ids"],
                order=order,
            )
        )
    return topics
