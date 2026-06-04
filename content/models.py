from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict


@dataclass
class Topic:
    topic_id: str
    title: str
    summary: str
    source_section_ids: list[str]
    order: int


@dataclass
class Diagram:
    diagram_id: str
    diagram_type: str   # "mermaid" or "extracted_image"
    content: str        # Mermaid code string, or file path for images
    caption: str


@dataclass
class Question:
    question_id: str
    question_text: str
    question_type: str          # "single_choice" or "multiple_choice"
    options: list[str]          # exactly 4 options
    correct_answers: list[int]  # indices of correct option(s)
    explanation: str


@dataclass
class EnrichedTopic:
    topic: Topic
    content_md: str             # Enriched content in Markdown
    key_takeaways: list[str]
    diagrams: list[Diagram]
    inline_questions: list[Question]

    @classmethod
    def from_dict(cls, d: dict) -> EnrichedTopic:
        return cls(
            topic=Topic(**d["topic"]),
            content_md=d["content_md"],
            key_takeaways=d["key_takeaways"],
            diagrams=[Diagram(**x) for x in d["diagrams"]],
            inline_questions=[Question(**x) for x in d["inline_questions"]],
        )


@dataclass
class LearningModule:
    module_id: str
    title: str
    source_doc_id: str
    topics: list[EnrichedTopic]
    created_at: str             # ISO 8601

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_dict(cls, d: dict) -> LearningModule:
        return cls(
            module_id=d["module_id"],
            title=d["title"],
            source_doc_id=d["source_doc_id"],
            topics=[EnrichedTopic.from_dict(t) for t in d["topics"]],
            created_at=d["created_at"],
        )

    @classmethod
    def from_json(cls, s: str) -> LearningModule:
        return cls.from_dict(json.loads(s))
