from __future__ import annotations
import uuid

from content._utils import parse_json_response
from content.llm_client import LLMClient
from content.models import Topic
from ingestion.models import Document


def decompose(doc: Document, llm: LLMClient) -> list[Topic]:
    sections_text = "\n\n".join(
        f"[section_id: {s.section_id}]\n## {s.title}\n{s.body[:600]}"
        for s in doc.sections
    )

    system = (
        "You are an expert instructional designer. "
        "Decompose documents into focused, learnable sub-topics."
    )
    prompt = f"""Decompose the document below into 5-10 focused learning sub-topics.
Each sub-topic should cover one coherent concept and reference which section IDs it draws from.

Document title: {doc.title}

Sections:
{sections_text}

Return a JSON array (key "topics") like:
{{
  "topics": [
    {{
      "title": "Sub-topic title",
      "summary": "One-sentence summary",
      "source_section_ids": ["<exact section_id from above>"]
    }}
  ]
}}"""

    result = llm.generate(prompt, system, response_schema={})
    data = parse_json_response(result)

    if isinstance(data, dict):
        items = data.get("topics") or next(iter(data.values()), [])
    else:
        items = data

    valid_ids = {s.section_id for s in doc.sections}
    topics: list[Topic] = []
    for i, item in enumerate(items):
        raw_ids = item.get("source_section_ids", [])
        topics.append(
            Topic(
                topic_id=str(uuid.uuid4()),
                title=item["title"],
                summary=item.get("summary", ""),
                source_section_ids=[sid for sid in raw_ids if sid in valid_ids],
                order=i,
            )
        )

    return topics
