import uuid
import pytest
from backend.ingestion.models import Document, Section, SourceType
from backend.content.topic_decomposer import decompose


class MockLLMClient:
    def make_cached_document_blocks(self, text):
        return [{"type": "text", "text": text}]

    def generate(self, prompt, system=None, tool_schema=None, cached_blocks=None):
        return {
            "topics": [
                {
                    "title": "Introduction to ML",
                    "summary": "Basics of machine learning.",
                    "source_section_titles": ["Introduction to Machine Learning"],
                },
                {
                    "title": "Supervised vs Unsupervised",
                    "summary": "Comparison of learning paradigms.",
                    "source_section_titles": [
                        "Supervised Learning",
                        "Unsupervised Learning",
                    ],
                },
            ]
        }


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


def test_decompose_returns_topics():
    doc = _make_doc()
    topics = decompose(doc, MockLLMClient())
    assert len(topics) == 2


def test_topics_have_required_fields():
    doc = _make_doc()
    topics = decompose(doc, MockLLMClient())
    for t in topics:
        assert t.topic_id
        assert t.title
        assert t.summary
        assert isinstance(t.order, int)


def test_topics_ordered():
    doc = _make_doc()
    topics = decompose(doc, MockLLMClient())
    orders = [t.order for t in topics]
    assert orders == sorted(orders)


def test_source_section_ids_resolved():
    doc = _make_doc()
    topics = decompose(doc, MockLLMClient())
    # First topic maps to "Introduction to Machine Learning"
    assert len(topics[0].source_section_ids) == 1
    # Second topic maps to two sections
    assert len(topics[1].source_section_ids) == 2
