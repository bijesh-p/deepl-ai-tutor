"""End-to-end integration tests: all three providers × full pipeline.

Exercises: PDF parse → run_sliding_pipeline → generate_question_bank →
           tutor graph nodes (generate_diagnostic, evaluate_diagnostic,
           present_concept fast-path, ask_question, evaluate_response).

No live API calls are made. Each adapter's raw client is replaced with a
scriptable mock that returns schema-correct responses keyed by tool name.
TTS and ChromaDB calls are patched out.
"""
from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict

import pytest

from backend.content.models import EnrichedTopic, LearningModule, Topic
from backend.ingestion.models import Document, Section, SourceType
from backend.interactive_tutor import graph

# ---------------------------------------------------------------------------
# Canonical responses for every tool schema name used in the pipeline
# ---------------------------------------------------------------------------

_TOOL_RESPONSES: dict[str, dict] = {
    "assess_chunk": {
        "is_presentable": True,
        "concept_title": "Photosynthesis",
        "concept_summary": "Plants convert sunlight into chemical energy.",
        "reason": "enough explanatory content",
    },
    "return_diagram": {
        "diagram_type": "mermaid",
        "content": "graph LR A[Light] --> B[Chlorophyll] --> C[ATP]",
        "caption": "Light-driven ATP synthesis",
    },
    "return_key_bullets": {
        "bullets": ["Light is absorbed by chlorophyll", "ATP is produced", "Water is split"],
    },
    "return_enriched_topic": {
        "top_concepts": ["chlorophyll", "ATP"],
        "content_md": "# Photosynthesis\n\nPlants use light to make energy.",
        "key_takeaways": ["Light drives the reaction", "Oxygen is released"],
    },
    "return_questions": {
        "questions": [
            {
                "question_text": "What pigment absorbs light?",
                "question_type": "single_choice",
                "options": ["Chlorophyll", "Melanin", "Haemoglobin", "Keratin"],
                "correct_index": 0,
            },
            {
                "question_text": "What is produced by photosynthesis?",
                "question_type": "single_choice",
                "options": ["ATP", "CO2", "Nitrogen", "Iron"],
                "correct_index": 0,
            },
        ]
    },
    "return_question_bank": {
        "questions": [
            {
                "question_text": "What drives photosynthesis?",
                "question_type": "single_choice",
                "options": ["Light", "Heat", "Sound", "Gravity"],
                "correct_answers": [0],
                "explanation": "Light provides the energy for photosynthesis.",
                "difficulty": "easy",
                "topic_title": "Photosynthesis",
            }
        ]
    },
    "return_diagnostic_questions": {
        "questions": [
            {"question_text": "D1?", "options": ["A", "B", "C", "D"], "correct_index": 0},
            {"question_text": "D2?", "options": ["A", "B", "C", "D"], "correct_index": 1},
            {"question_text": "D3?", "options": ["A", "B", "C", "D"], "correct_index": 2},
        ]
    },
    "return_slide": {
        "top_concepts": ["chlorophyll"],
        "transcript": "Photosynthesis converts light energy into chemical energy.",
        "mermaid_code": "",
    },
    "generate_question": {
        "question": "What molecule absorbs light in photosynthesis?",
        "expected_answer": "Chlorophyll",
        "misconceptions": ["ATP", "Glucose"],
    },
    "evaluate_answer": {
        "is_correct": True,
        "feedback": "Correct! Chlorophyll is the key light-absorbing pigment.",
        "misconception_identified": "",
    },
}


# ---------------------------------------------------------------------------
# Mock clients — one per wire format
# ---------------------------------------------------------------------------

class _AnthropicScriptableClient:
    """Mimics anthropic.Anthropic().messages — returns tool_use blocks."""

    @property
    def messages(self):
        return self

    def create(self, **kwargs):
        tools = kwargs.get("tools", [])
        if tools:
            name = tools[0]["name"]
            tool_input = _TOOL_RESPONSES.get(name, {})
            block = type("Block", (), {"type": "tool_use", "input": tool_input})()
            return type("Resp", (), {"content": [block], "stop_reason": "tool_use"})()
        block = type("Block", (), {"type": "text", "text": "ok"})()
        return type("Resp", (), {"content": [block], "stop_reason": "end_turn"})()


class _OllamaScriptableClient:
    """Mimics openai.OpenAI().chat.completions — returns tool_calls with JSON args."""

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        tools = kwargs.get("tools", [])
        if tools:
            name = tools[0]["function"]["name"]
            payload = _TOOL_RESPONSES.get(name, {})
            fn = type("Function", (), {"arguments": json.dumps(payload)})()
            tc = type("ToolCall", (), {"function": fn})()
            message = type("Message", (), {"content": None, "tool_calls": [tc]})()
        else:
            message = type("Message", (), {"content": "ok", "tool_calls": None})()
        choice = type("Choice", (), {"message": message})()
        return type("Resp", (), {"choices": [choice]})()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_doc(n_words: int = 300) -> Document:
    body = " ".join(["word"] * n_words)
    return Document(
        doc_id="doc-e2e",
        title="E2E Test Document",
        source_filename="e2e.pdf",
        source_type=SourceType.PDF,
        sections=[Section(section_id="s1", title="Introduction", body=body, level=1)],
        total_pages=1,
    )


class _NoopSpan:
    def __enter__(self): return self
    def __exit__(self, *_): pass


class _NoopTracer:
    def start_as_current_span(self, *a, **kw): return _NoopSpan()


def _make_progress() -> dict:
    return {
        "enriched_topics": [],
        "topics_enriched": 0,
        "ready": False,
        "module_id": str(uuid.uuid4()),
        "audio_enabled": False,
        "detail": "",
    }


# ---------------------------------------------------------------------------
# Provider fixture (parametrised over all three)
# ---------------------------------------------------------------------------

@pytest.fixture(params=["anthropic", "portkey", "ollama"])
def scripted_llm(request, monkeypatch):
    """Return an adapter for the given provider with its raw client replaced
    by a scriptable mock.  TTS and ChromaDB calls are patched out."""
    provider = request.param

    # Suppress TTS
    monkeypatch.setattr(
        "backend.content.audio_generator.generate_audio", lambda *a, **kw: "", raising=False
    )
    monkeypatch.setattr(
        "backend.content.audio_generator.generate_diagnostic_audio", lambda *a, **kw: "", raising=False
    )
    # Suppress vector-store upsert
    monkeypatch.setattr(
        "backend.content.sliding_pipeline._store_in_vector_db", lambda *a, **kw: None, raising=False
    )

    if provider == "anthropic":
        from backend.core.llm_client.adapters.anthropic_adapter import AnthropicAdapter
        adapter = AnthropicAdapter.__new__(AnthropicAdapter)
        adapter.provider = "anthropic"
        adapter.model = "claude-sonnet-4-6"
        adapter._client = _AnthropicScriptableClient()
        return adapter

    if provider == "portkey":
        from backend.core.llm_client.adapters.portkey_adapter import PortkeyAdapter
        adapter = PortkeyAdapter.__new__(PortkeyAdapter)
        adapter.provider = "portkey"
        adapter.model = "@vertexai-global/anthropic.claude-sonnet-4-6"
        adapter._client = _AnthropicScriptableClient()  # same wire format as Anthropic
        return adapter

    # ollama
    from backend.core.llm_client.adapters.ollama_adapter import OllamaAdapter
    adapter = OllamaAdapter.__new__(OllamaAdapter)
    adapter.provider = "ollama"
    adapter.model = "llama3.2"
    adapter._client = _OllamaScriptableClient()
    return adapter


# ---------------------------------------------------------------------------
# E2E test
# ---------------------------------------------------------------------------

def test_pipeline_to_quiz_to_tutor(scripted_llm, monkeypatch):
    """Full flow for one provider: pipeline → quiz → tutor graph."""

    # ── 1. Sliding pipeline ──────────────────────────────────────────────────
    from backend.content.sliding_pipeline import run_sliding_pipeline

    doc = _make_doc(n_words=300)
    progress = _make_progress()
    abort = threading.Event()

    enriched_topics = run_sliding_pipeline(
        doc, scripted_llm, progress, abort, _NoopTracer()
    )

    assert len(enriched_topics) >= 1, "Pipeline should publish at least one topic"
    assert progress["ready"] is True, "progress['ready'] should be set after first topic"
    assert progress["topics_enriched"] >= 1

    first_topic = enriched_topics[0]
    assert first_topic.topic.title == "Photosynthesis"
    assert first_topic.content_md  # non-empty

    # ── 2. Quiz bank generation ──────────────────────────────────────────────
    from backend.quiz.question_bank import generate_question_bank

    module = LearningModule(
        module_id=progress["module_id"],
        title=doc.title,
        source_doc_id=doc.doc_id,
        topics=enriched_topics,
        created_at="2026-01-01T00:00:00+00:00",
    )

    bank = generate_question_bank(module, scripted_llm)
    assert len(bank.questions) >= 1

    # ── 3. Tutor graph nodes ─────────────────────────────────────────────────
    monkeypatch.setattr(graph, "_get_llm", lambda: scripted_llm)
    monkeypatch.setattr(graph, "_retrieve_context", lambda *a, **kw: "")

    # 3a. generate_diagnostic
    state: graph.GraphState = {
        "current_concept": first_topic.topic.title,
        "concept_summary": first_topic.topic.summary,
        "chat_history": [],
    }
    state.update(graph.generate_diagnostic(state))

    assert len(state["diagnostic_questions"]) == 3

    # 3b. evaluate_diagnostic (all correct → advanced)
    state["diagnostic_answers"] = [0, 1, 2]
    state.update(graph.evaluate_diagnostic(state))
    assert state["presentation_depth"] == "advanced"

    # 3c. present_concept — fast path (enrich already done by pipeline)
    state["enriched_topic"] = asdict(first_topic)
    state["concept_content"] = ""
    state["module_id"] = module.module_id
    state["audio_enabled"] = False
    state.update(graph.present_concept(state))

    slide = next(m for m in state["chat_history"] if m.get("role") == "slide")
    assert slide["concept"] == first_topic.topic.title
    assert slide["transcript"]  # non-empty

    # 3d. ask_question
    state["attempts"] = 0
    state["feedback"] = ""
    state.update(graph.ask_question(state))

    q = state["current_question"]
    assert q["question"]
    assert q["expected_answer"]

    # 3e. evaluate_response
    state["student_answer"] = "Chlorophyll"
    state.update(graph.evaluate_response(state))

    assert state["concept_mastered"] is True
    assert state["feedback"]
