from __future__ import annotations

import uuid
from backend.content.llm_client import LLMClient, coerce_tool_array, coerce_tool_item
from backend.content.models import Topic
from backend.ingestion.models import Document

_TOOL_SCHEMA = {
    "name": "return_topics",
    "description": "Return an ordered list of learning topics derived from the document.",
    "input_schema": {
        "type": "object",
        "properties": {
            "topics": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "summary": {"type": "string"},
                        "source_section_titles": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["title", "summary", "source_section_titles"],
                },
            }
        },
        "required": ["topics"],
    },
}

_SYSTEM = (
    "You are an expert instructional designer. "
    "Given a document's sections, identify 3-8 coherent learning topics. "
    "Each topic should cover one focused concept. "
    "Return them in a logical learning sequence."
)


def decompose(doc: Document, llm: LLMClient) -> list[Topic]:
    """Break a Document into an ordered list of learning Topics."""
    section_text = _format_sections(doc)
    cached_blocks = llm.make_cached_document_blocks(section_text)

    prompt = (
        "Above is the document content. "
        "Identify the key learning topics and return them using the provided tool."
    )

    result = llm.generate(
        prompt=prompt,
        system=_SYSTEM,
        tool_schema=_TOOL_SCHEMA,
        cached_blocks=cached_blocks,
    )

    section_id_map = {s.title: s.section_id for s in doc.sections}

    topics: list[Topic] = []
    for i, item in enumerate(coerce_tool_array(result["topics"])):
        item = coerce_tool_item(item)
        source_ids = [
            section_id_map[t]
            for t in item["source_section_titles"]
            if t in section_id_map
        ]
        topics.append(
            Topic(
                topic_id=str(uuid.uuid4()),
                title=item["title"],
                summary=item["summary"],
                source_section_ids=source_ids,
                order=i,
            )
        )

    return topics


def _format_sections(doc: Document) -> str:
    parts = [f"Document: {doc.title}\n"]
    for s in doc.sections:
        parts.append(f"## {s.title}\n{s.body}")
    return "\n\n".join(parts)
