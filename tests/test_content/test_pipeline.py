"""Tests for the sliding_pipeline enrichment path.

run_sliding_pipeline is the production pipeline; this test exercises
_enrich_one (enrich + diagrams + questions) via the same mock LLM
used in the old pipeline tests.
"""
import threading
import uuid
import pytest
from backend.ingestion.models import Document, Section, SourceType
from backend.content.sliding_pipeline import _enrich_one, _make_topic, _assess
from backend.content.models import LearningModule, Topic


class MockLLMClient:
    def make_cached_document_blocks(self, text):
        return [{"type": "text", "text": text}]

    def generate(self, prompt, system=None, tool_schema=None, cached_blocks=None):
        name = tool_schema["name"] if tool_schema else ""

        if name == "assess_chunk":
            return {
                "is_presentable": True,
                "concept_title": "ML Basics",
                "concept_summary": "Introduction to machine learning concepts.",
                "reason": "Contains enough material.",
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


class _NoopSpan:
    def __enter__(self): return self
    def __exit__(self, *_): pass


class _NoopTracer:
    def start_as_current_span(self, name, **kw): return _NoopSpan()


def _make_topic_fixture():
    return Topic(
        topic_id=str(uuid.uuid4()),
        title="ML Basics",
        summary="Introduction to machine learning concepts.",
        source_section_ids=[str(uuid.uuid4())],
        order=0,
    )


def _enrich(topic=None):
    t = topic or _make_topic_fixture()
    return _enrich_one(
        t,
        "Machine learning is a subset of AI. It learns from data.",
        MockLLMClient(),
        _NoopTracer(),
        threading.Event(),
    )


def test_enrich_returns_enriched_topic():
    et = _enrich()
    assert et is not None
    assert et.content_md


def test_enrich_has_content_and_takeaways():
    et = _enrich()
    assert et.content_md
    assert len(et.key_takeaways) >= 1


def test_enrich_has_questions():
    et = _enrich()
    assert len(et.inline_questions) == 2


def test_enrich_has_diagram():
    et = _enrich()
    assert len(et.diagrams) == 1
    assert et.diagrams[0].diagram_type == "mermaid"


def test_module_json_roundtrip():
    et = _enrich()
    module = LearningModule(
        module_id=str(uuid.uuid4()),
        title="Test Module",
        source_doc_id=str(uuid.uuid4()),
        topics=[et],
        created_at="2026-01-01T00:00:00+00:00",
    )
    restored = LearningModule.from_json(module.to_json())
    assert restored.module_id == module.module_id
    assert len(restored.topics) == 1
    assert restored.topics[0].topic.title == et.topic.title
    assert restored.topics[0].content_md == et.content_md
    assert len(restored.topics[0].diagrams) == len(et.diagrams)
    assert len(restored.topics[0].inline_questions) == len(et.inline_questions)
