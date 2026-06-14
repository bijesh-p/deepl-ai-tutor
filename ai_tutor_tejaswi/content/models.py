from __future__ import annotations
from dataclasses import dataclass, field


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
    content: str        # Mermaid code string, or file path for extracted images
    caption: str


@dataclass
class Question:
    question_id: str
    question_text: str
    question_type: str              # "single_choice" or "multiple_choice"
    options: list[str]              # 4 options
    correct_answers: list[int]      # indices of correct option(s)
    explanation: str


@dataclass
class EnrichedTopic:
    topic: Topic
    content_html: str               # Markdown content
    key_takeaways: list[str]
    diagrams: list[Diagram] = field(default_factory=list)
    inline_questions: list[Question] = field(default_factory=list)


@dataclass
class LearningModule:
    module_id: str
    title: str
    source_doc_id: str
    topics: list[EnrichedTopic]
    created_at: str                 # ISO 8601
