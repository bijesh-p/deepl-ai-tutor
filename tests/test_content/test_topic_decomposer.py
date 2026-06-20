"""Tests for sliding_pipeline._assess and _make_topic.

These replace the old topic_decomposer tests — the decompose step was
removed when the sliding-window pipeline was adopted.
"""
import uuid
from backend.ingestion.models import Document, Section, SourceType
from backend.content.sliding_pipeline import _assess, _make_topic


class _MockLLM:
    def generate(self, prompt, system=None, tool_schema=None, cached_blocks=None):
        return {
            "is_presentable": True,
            "concept_title": "Neural Networks",
            "concept_summary": "How neural networks learn from data.",
            "reason": "Contains enough material.",
        }


class _MockLLMNotPresentable:
    def generate(self, prompt, system=None, tool_schema=None, cached_blocks=None):
        return {
            "is_presentable": False,
            "concept_title": "",
            "concept_summary": "",
            "reason": "Only a table of contents.",
        }


def _words(text: str, section_id: str) -> list[tuple[str, str]]:
    return [(w, section_id) for w in text.split()]


def test_assess_returns_dict():
    sid = str(uuid.uuid4())
    words = _words("Deep learning uses layers of neurons to learn patterns.", sid)
    result = _assess(_MockLLM(), words)
    assert isinstance(result, dict)


def test_assess_presentable_true():
    sid = str(uuid.uuid4())
    words = _words("Deep learning uses layers of neurons.", sid)
    result = _assess(_MockLLM(), words)
    assert result.get("is_presentable") is True
    assert result.get("concept_title")


def test_assess_presentable_false():
    sid = str(uuid.uuid4())
    words = _words("Contents. 1. Introduction. 2. Methods.", sid)
    result = _assess(_MockLLMNotPresentable(), words)
    assert result.get("is_presentable") is False


def test_assess_handles_exception_gracefully():
    class _BrokenLLM:
        def generate(self, *a, **kw):
            raise RuntimeError("API error")

    sid = str(uuid.uuid4())
    words = _words("Some text.", sid)
    result = _assess(_BrokenLLM(), words)
    assert isinstance(result, dict)
    # fail-open: on error the pipeline defaults to presentable so force-publish fires
    assert result.get("is_presentable") is True


def test_make_topic_fields():
    sid1, sid2 = str(uuid.uuid4()), str(uuid.uuid4())
    words = _words("word1 word2", sid1) + _words("word3 word4", sid2)
    assessment = {
        "concept_title": "Backpropagation",
        "concept_summary": "How gradients flow backward.",
    }
    topic = _make_topic(assessment, words, idx=0)
    assert topic.title == "Backpropagation"
    assert topic.summary == "How gradients flow backward."
    assert topic.order == 0
    assert sid1 in topic.source_section_ids
    assert sid2 in topic.source_section_ids


def test_make_topic_deduplicates_section_ids():
    sid = str(uuid.uuid4())
    words = _words("word1 word2 word3", sid)
    assessment = {"concept_title": "Topic", "concept_summary": "Summary."}
    topic = _make_topic(assessment, words, idx=1)
    assert topic.source_section_ids.count(sid) == 1
