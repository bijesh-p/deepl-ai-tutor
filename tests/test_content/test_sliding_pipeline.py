"""Tests for the sliding-window content pipeline.

Covers:
- _enrich_one falls back to raw text when enrich() raises
- _enrich_one returns EnrichedTopic on success
- run_sliding_pipeline publishes topics and updates progress dict
- run_sliding_pipeline skips a failed topic and continues enriching the rest
"""
from __future__ import annotations

import threading
import uuid
from unittest.mock import MagicMock, patch

from backend.content.models import Diagram, EnrichedTopic, Topic
from backend.content.sliding_pipeline import _enrich_one, run_sliding_pipeline
from backend.ingestion.models import Document, Section, SourceType


class _NoopSpan:
    def __enter__(self): return self
    def __exit__(self, *_): pass


class _NoopTracer:
    def start_as_current_span(self, *a, **kw): return _NoopSpan()


def _make_topic(title: str = "Test Topic", idx: int = 0) -> Topic:
    return Topic(
        topic_id=str(uuid.uuid4()),
        title=title,
        summary="A summary.",
        source_section_ids=["s1"],
        order=idx,
    )


def _make_enriched(topic: Topic) -> EnrichedTopic:
    return EnrichedTopic(
        topic=topic,
        content_md="# Test\n\nContent.",
        key_takeaways=["Key 1"],
        diagrams=[],
        inline_questions=[],
        top_concepts=["concept_a"],
        audio_path="",
    )


def _make_stub_anchor():
    from backend.content.diagram_generator import SlideAnchor
    return SlideAnchor(diagram=None, bullets=["Point 1", "Point 2"])


def _make_doc(n_words: int = 300) -> Document:
    body = " ".join(["word"] * n_words)
    return Document(
        doc_id="doc-1",
        title="Test Doc",
        source_filename="test.pdf",
        source_type=SourceType.PDF,
        sections=[Section(section_id="s1", title="Intro", body=body, level=1)],
        total_pages=1,
    )


def _progress() -> dict:
    return {
        "enriched_topics": [],
        "topics_enriched": 0,
        "ready": False,
        "module_id": "mod-1",
        "audio_enabled": False,
        "detail": "",
    }


# ---------------------------------------------------------------------------
# _enrich_one
# ---------------------------------------------------------------------------

def test_enrich_one_falls_back_to_raw_text_when_enrich_raises():
    """enrich() failure uses raw-text fallback rather than returning None."""
    topic = _make_topic()

    with (
        patch(
            "backend.content.diagram_generator.generate_slide_anchor",
            return_value=_make_stub_anchor(),
        ),
        patch(
            "backend.content.content_enricher.enrich",
            side_effect=RuntimeError("LLM unavailable"),
        ),
    ):
        result = _enrich_one(
            topic, "source text", MagicMock(), _NoopTracer(), threading.Event(),
            audio_enabled=False,
        )

    assert result is not None
    assert isinstance(result, EnrichedTopic)
    assert result.topic == topic


def test_enrich_one_returns_enriched_topic_on_success():
    topic = _make_topic()
    expected = _make_enriched(topic)

    with (
        patch(
            "backend.content.diagram_generator.generate_slide_anchor",
            return_value=_make_stub_anchor(),
        ),
        patch("backend.content.content_enricher.enrich", return_value=expected),
        patch(
            "backend.content.inline_question_gen.generate_inline_questions",
            return_value=[],
        ),
    ):
        result = _enrich_one(
            topic, "source text", MagicMock(), _NoopTracer(), threading.Event(),
            audio_enabled=False,
        )

    assert result is not None
    assert result.topic.title == topic.title
    assert "Point 1" in result.content_md  # bullets prepended (no diagram)


def test_enrich_one_returns_none_when_aborted():
    topic = _make_topic()
    abort = threading.Event()
    abort.set()

    result = _enrich_one(topic, "text", MagicMock(), _NoopTracer(), abort, audio_enabled=False)

    assert result is None


# ---------------------------------------------------------------------------
# run_sliding_pipeline
# ---------------------------------------------------------------------------

def test_run_sliding_pipeline_returns_topics():
    doc = _make_doc(n_words=300)
    topic = _make_topic()
    enriched = _make_enriched(topic)
    prog = _progress()

    with (
        patch(
            "backend.content.sliding_pipeline._assess",
            return_value={"is_presentable": True, "concept_title": "Test", "concept_summary": "S", "reason": "ok"},
        ),
        patch("backend.content.sliding_pipeline._enrich_one", return_value=enriched),
        patch("backend.content.sliding_pipeline._store_in_vector_db"),
    ):
        result = run_sliding_pipeline(doc, MagicMock(), prog, threading.Event(), _NoopTracer())

    assert len(result) >= 1
    assert result[0].topic.title == topic.title


def test_run_sliding_pipeline_updates_progress():
    doc = _make_doc(n_words=300)
    enriched = _make_enriched(_make_topic())
    prog = _progress()

    with (
        patch(
            "backend.content.sliding_pipeline._assess",
            return_value={"is_presentable": True, "concept_title": "T", "concept_summary": "S", "reason": "ok"},
        ),
        patch("backend.content.sliding_pipeline._enrich_one", return_value=enriched),
        patch("backend.content.sliding_pipeline._store_in_vector_db"),
    ):
        run_sliding_pipeline(doc, MagicMock(), prog, threading.Event(), _NoopTracer())

    assert len(prog["enriched_topics"]) >= 1
    assert prog["topics_enriched"] >= 1
    assert prog["ready"] is True


def test_run_sliding_pipeline_skips_failed_topic_and_continues():
    """One None return from _enrich_one does not stop the pipeline."""
    doc = Document(
        doc_id="doc-2",
        title="Multi",
        source_filename="m.pdf",
        source_type=SourceType.PDF,
        sections=[
            Section(section_id="s1", title="A", body=" ".join(["word"] * 200), level=1),
            Section(section_id="s2", title="B", body=" ".join(["word"] * 200), level=1),
        ],
        total_pages=2,
    )
    good_topic = _make_topic("Topic B", idx=1)
    good_enriched = _make_enriched(good_topic)
    prog = _progress()

    enrich_results = iter([None, good_enriched])

    with (
        patch(
            "backend.content.sliding_pipeline._assess",
            return_value={"is_presentable": True, "concept_title": "T", "concept_summary": "S", "reason": "ok"},
        ),
        patch("backend.content.sliding_pipeline._enrich_one", side_effect=enrich_results),
        patch("backend.content.sliding_pipeline._store_in_vector_db"),
    ):
        result = run_sliding_pipeline(doc, MagicMock(), prog, threading.Event(), _NoopTracer())

    assert len(result) == 1
    assert result[0].topic.title == "Topic B"


def test_run_sliding_pipeline_aborts_cleanly():
    doc = _make_doc(n_words=300)
    prog = _progress()
    abort = threading.Event()
    abort.set()

    with patch("backend.content.sliding_pipeline._assess") as mock_assess:
        result = run_sliding_pipeline(doc, MagicMock(), prog, abort, _NoopTracer())

    mock_assess.assert_not_called()
    assert result == []
