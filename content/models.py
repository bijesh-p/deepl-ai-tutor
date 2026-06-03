from __future__ import annotations

import json
import dataclasses
from dataclasses import dataclass, field


@dataclass
class Topic:
    topic_id: str
    title: str
    summary: str
    source_section_ids: list[str]
    order: int  # position in learning sequence


@dataclass
class Diagram:
    diagram_id: str
    diagram_type: str   # "mermaid" or "extracted_image"
    content: str        # Mermaid code string or file path for images
    caption: str


@dataclass
class Question:
    question_id: str
    question_text: str
    question_type: str          # "single_choice" or "multiple_choice"
    options: list[str]          # 4 options
    correct_answers: list[int]  # indices of correct option(s)
    explanation: str


@dataclass
class EnrichedTopic:
    topic: Topic
    content_md: str             # enriched content in Markdown
    key_takeaways: list[str]
    diagrams: list[Diagram]
    inline_questions: list[Question]


@dataclass
class LearningModule:
    module_id: str
    title: str
    source_doc_id: str
    topics: list[EnrichedTopic]
    created_at: str  # ISO 8601

    def to_json(self) -> str:
        return json.dumps(dataclasses.asdict(self), indent=2)

    @classmethod
    def from_json(cls, data: str | dict) -> LearningModule:
        d = json.loads(data) if isinstance(data, str) else data
        topics = [
            EnrichedTopic(
                topic=Topic(**t["topic"]),
                content_md=t["content_md"],
                key_takeaways=t["key_takeaways"],
                diagrams=[Diagram(**diag) for diag in t["diagrams"]],
                inline_questions=[Question(**q) for q in t["inline_questions"]],
            )
            for t in d["topics"]
        ]
        return cls(
            module_id=d["module_id"],
            title=d["title"],
            source_doc_id=d["source_doc_id"],
            topics=topics,
            created_at=d["created_at"],
        )
