import uuid
import pytest
from backend.ingestion.models import Document, Section, SourceType
from backend.content.pipeline import run_pipeline
from backend.content.models import LearningModule


class MockLLMClient:
    def make_cached_document_blocks(self, text):
        return [{"type": "text", "text": text}]

    def generate(self, prompt, system=None, tool_schema=None, cached_blocks=None):
        name = tool_schema["name"] if tool_schema else ""

        if name == "return_topics":
            return {
                "topics": [
                    {
                        "title": "ML Basics",
                        "summary": "Introduction to machine learning concepts.",
                        "source_section_titles": ["Introduction to Machine Learning"],
                    },
                    {
                        "title": "Learning Paradigms",
                        "summary": "Supervised vs unsupervised learning.",
                        "source_section_titles": [
                            "Supervised Learning",
                            "Unsupervised Learning",
                        ],
                    },
                ]
            }

        if name == "return_enriched_topic":
            return {
                "content_md": "## Overview\nThis topic covers machine learning fundamentals.",
                "key_takeaways": ["ML learns from data", "Models generalise"],
            }

        if name == "return_diagram":
            return {
                "needs_diagram": True,
                "mermaid_code": "graph TD\n  A[Data] --> B[Model]",
                "caption": "Data to model flow",
            }

        if name == "return_questions":
            return {
                "questions": [
                    {
                        "question_text": "What does ML stand for?",
                        "question_type": "single_choice",
                        "options": ["Machine Learning", "Model Logic", "Meta Layer", "Math Logic"],
                        "correct_answers": [0],
                        "explanation": "ML stands for Machine Learning.",
                    },
                    {
                        "question_text": "Which are supervised tasks?",
                        "question_type": "multiple_choice",
                        "options": ["Classification", "Clustering", "Regression", "Dimensionality Reduction"],
                        "correct_answers": [0, 2],
                        "explanation": "Classification and regression are supervised.",
                    },
                ]
            }

        return ""


def _make_doc():
    return Document(
        doc_id=str(uuid.uuid4()),
        title="Sample ML Document",
        source_filename="sample.pdf",
        source_type=SourceType.PDF,
        total_pages=3,
        sections=[
            Section(str(uuid.uuid4()), "Introduction to Machine Learning", "ML basics.", 1),
            Section(str(uuid.uuid4()), "Supervised Learning", "Labelled data.", 1),
            Section(str(uuid.uuid4()), "Unsupervised Learning", "No labels.", 1),
        ],
    )


def test_pipeline_returns_module():
    module = run_pipeline(_make_doc(), MockLLMClient())
    assert isinstance(module, LearningModule)


def test_module_has_topics():
    module = run_pipeline(_make_doc(), MockLLMClient())
    assert len(module.topics) == 2


def test_each_topic_has_content_and_questions():
    module = run_pipeline(_make_doc(), MockLLMClient())
    for et in module.topics:
        assert et.content_md
        assert len(et.key_takeaways) >= 1
        assert len(et.inline_questions) == 2


def test_each_topic_has_diagram():
    module = run_pipeline(_make_doc(), MockLLMClient())
    for et in module.topics:
        assert len(et.diagrams) == 1
        assert et.diagrams[0].diagram_type == "mermaid"


def test_module_json_roundtrip():
    module = run_pipeline(_make_doc(), MockLLMClient())
    restored = LearningModule.from_json(module.to_json())
    assert restored.module_id == module.module_id
    assert restored.title == module.title
    assert len(restored.topics) == len(module.topics)
    for orig, rest in zip(module.topics, restored.topics):
        assert rest.topic.title == orig.topic.title
        assert rest.content_md == orig.content_md
        assert len(rest.diagrams) == len(orig.diagrams)
        assert len(rest.inline_questions) == len(orig.inline_questions)
