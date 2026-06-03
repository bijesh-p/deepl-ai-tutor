from __future__ import annotations

import json
from pathlib import Path

import pytest

from content.llm_client import LLMClient, Provider
from content.topic_decomposer import decompose
from content.content_enricher import enrich
from content.diagram_generator import generate_diagrams
from content.inline_question_gen import generate_inline_questions
from content.models import EnrichedTopic, LearningModule, Topic
from ingestion.models import Document

FIXTURES = Path(__file__).parent.parent / "fixtures"


# ---------------------------------------------------------------------------
# MockLLMClient — configurable per-call response queue
# ---------------------------------------------------------------------------

class MockLLMClient:
    """Returns pre-configured JSON responses in order of generate() calls."""

    def __init__(self, responses: list):
        self._queue = list(responses)

    def generate(self, prompt: str, system=None, response_schema=None):
        if not self._queue:
            raise RuntimeError("MockLLMClient: no more responses queued")
        return self._queue.pop(0)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_doc() -> Document:
    return Document.from_json((FIXTURES / "sample_document.json").read_text())


@pytest.fixture
def sample_module() -> LearningModule:
    return LearningModule.from_json((FIXTURES / "sample_module.json").read_text())


DECOMPOSE_RESPONSE = [
    {
        "title": "How Neural Networks Learn",
        "summary": "Neural networks learn by adjusting weights through backpropagation.",
        "source_section_ids": ["sec-001", "sec-003"],
    },
    {
        "title": "Preventing Overfitting",
        "summary": "Regularisation techniques prevent models from memorising training data.",
        "source_section_ids": ["sec-002", "sec-004"],
    },
]

ENRICH_RESPONSE = {
    "content_md": "## How Neural Networks Learn\n\nNeural networks adjust weights...",
    "key_takeaways": [
        "Backpropagation computes gradients layer by layer.",
        "An optimizer uses gradients to update weights.",
    ],
}

DIAGRAM_RESPONSE = {
    "needs_diagram": True,
    "mermaid_code": "---\ntitle: Training Loop\n---\nflowchart LR\n    A --> B",
    "caption": "The training loop",
}

DIAGRAM_NONE_RESPONSE = {
    "needs_diagram": False,
}

QUESTIONS_RESPONSE = [
    {
        "question_text": "What does backpropagation compute?",
        "question_type": "single_choice",
        "options": ["Predictions", "Gradients", "Weights", "Losses"],
        "correct_answers": [1],
        "explanation": "Backpropagation computes gradients of the loss w.r.t. each weight.",
    },
    {
        "question_text": "Which are regularisation techniques?",
        "question_type": "multiple_choice",
        "options": ["Dropout", "ReLU", "L2", "Softmax"],
        "correct_answers": [0, 2],
        "explanation": "Dropout and L2 regularisation reduce overfitting; ReLU and Softmax are activations.",
    },
]


# ---------------------------------------------------------------------------
# topic_decomposer tests
# ---------------------------------------------------------------------------

def test_decompose_returns_topics(sample_doc):
    llm = MockLLMClient([DECOMPOSE_RESPONSE])
    topics = decompose(sample_doc, llm)
    assert len(topics) == 2


def test_decompose_topic_fields(sample_doc):
    llm = MockLLMClient([DECOMPOSE_RESPONSE])
    topics = decompose(sample_doc, llm)
    t = topics[0]
    assert t.title == "How Neural Networks Learn"
    assert t.order == 1
    assert "sec-001" in t.source_section_ids


def test_decompose_assigns_unique_ids(sample_doc):
    llm = MockLLMClient([DECOMPOSE_RESPONSE])
    topics = decompose(sample_doc, llm)
    ids = [t.topic_id for t in topics]
    assert len(ids) == len(set(ids))


def test_decompose_order_sequential(sample_doc):
    llm = MockLLMClient([DECOMPOSE_RESPONSE])
    topics = decompose(sample_doc, llm)
    assert [t.order for t in topics] == list(range(1, len(topics) + 1))


# ---------------------------------------------------------------------------
# content_enricher tests
# ---------------------------------------------------------------------------

def test_enrich_returns_enriched_topic(sample_doc):
    llm = MockLLMClient([ENRICH_RESPONSE])
    topic = Topic(
        topic_id="t-1",
        title="How Neural Networks Learn",
        summary="Networks learn via backpropagation.",
        source_section_ids=["sec-001"],
        order=1,
    )
    enriched = enrich(topic, sample_doc, llm)
    assert isinstance(enriched, EnrichedTopic)
    assert enriched.content_md.startswith("##")
    assert len(enriched.key_takeaways) >= 1


def test_enrich_preserves_topic(sample_doc):
    llm = MockLLMClient([ENRICH_RESPONSE])
    topic = Topic("t-1", "Title", "Summary", ["sec-001"], 1)
    enriched = enrich(topic, sample_doc, llm)
    assert enriched.topic is topic


def test_enrich_diagrams_and_questions_empty_initially(sample_doc):
    llm = MockLLMClient([ENRICH_RESPONSE])
    topic = Topic("t-1", "Title", "Summary", ["sec-001"], 1)
    enriched = enrich(topic, sample_doc, llm)
    assert enriched.diagrams == []
    assert enriched.inline_questions == []


# ---------------------------------------------------------------------------
# diagram_generator tests
# ---------------------------------------------------------------------------

@pytest.fixture
def enriched_topic(sample_doc) -> EnrichedTopic:
    llm = MockLLMClient([ENRICH_RESPONSE])
    topic = Topic("t-1", "How Neural Networks Learn", "Summary", ["sec-001"], 1)
    return enrich(topic, sample_doc, llm)


def test_generate_diagrams_with_mermaid(enriched_topic):
    llm = MockLLMClient([DIAGRAM_RESPONSE])
    diagrams = generate_diagrams(enriched_topic, llm)
    assert len(diagrams) == 1
    assert diagrams[0].diagram_type == "mermaid"
    assert "flowchart" in diagrams[0].content


def test_generate_diagrams_none_needed(enriched_topic):
    llm = MockLLMClient([DIAGRAM_NONE_RESPONSE])
    diagrams = generate_diagrams(enriched_topic, llm)
    assert diagrams == []


def test_generate_diagrams_includes_extracted_images(enriched_topic):
    from ingestion.models import ExtractedImage
    llm = MockLLMClient([DIAGRAM_NONE_RESPONSE])
    img = ExtractedImage("img-1", "data/img.png", "A figure", "page 1")
    diagrams = generate_diagrams(enriched_topic, llm, extracted_images=[img])
    assert len(diagrams) == 1
    assert diagrams[0].diagram_type == "extracted_image"
    assert diagrams[0].content == "data/img.png"


# ---------------------------------------------------------------------------
# inline_question_gen tests
# ---------------------------------------------------------------------------

def test_generate_inline_questions_count(enriched_topic):
    llm = MockLLMClient([QUESTIONS_RESPONSE])
    questions = generate_inline_questions(enriched_topic, llm)
    assert 1 <= len(questions) <= 3


def test_generate_inline_questions_fields(enriched_topic):
    llm = MockLLMClient([QUESTIONS_RESPONSE])
    questions = generate_inline_questions(enriched_topic, llm)
    q = questions[0]
    assert q.question_text
    assert q.question_type in ("single_choice", "multiple_choice")
    assert len(q.options) == 4
    assert isinstance(q.correct_answers, list)
    assert q.explanation


def test_generate_inline_questions_unique_ids(enriched_topic):
    llm = MockLLMClient([QUESTIONS_RESPONSE])
    questions = generate_inline_questions(enriched_topic, llm)
    ids = [q.question_id for q in questions]
    assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Full pipeline: Document → LearningModule
# ---------------------------------------------------------------------------

def test_full_pipeline_document_to_module(sample_doc):
    """End-to-end: Document → topics → enrich → diagrams → questions → LearningModule."""
    import uuid
    from datetime import datetime, timezone

    llm = MockLLMClient([
        DECOMPOSE_RESPONSE,         # decompose()
        ENRICH_RESPONSE,            # enrich() topic 1
        DIAGRAM_RESPONSE,           # generate_diagrams() topic 1
        QUESTIONS_RESPONSE,         # inline_questions() topic 1
        ENRICH_RESPONSE,            # enrich() topic 2
        DIAGRAM_NONE_RESPONSE,      # generate_diagrams() topic 2
        QUESTIONS_RESPONSE,         # inline_questions() topic 2
    ])

    topics = decompose(sample_doc, llm)
    enriched_topics = []
    for topic in topics:
        et = enrich(topic, sample_doc, llm)
        et.diagrams = generate_diagrams(et, llm)
        et.inline_questions = generate_inline_questions(et, llm)
        enriched_topics.append(et)

    module = LearningModule(
        module_id=str(uuid.uuid4()),
        title=sample_doc.title,
        source_doc_id=sample_doc.doc_id,
        topics=enriched_topics,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    assert len(module.topics) == 2
    assert all(et.content_md for et in module.topics)
    assert all(et.key_takeaways for et in module.topics)
    assert module.topics[0].diagrams  # topic 1 has a diagram
    assert module.topics[1].diagrams == []  # topic 2 has none

    # Verify serialisation round-trip
    restored = LearningModule.from_json(module.to_json())
    assert restored.module_id == module.module_id
    assert len(restored.topics) == 2
