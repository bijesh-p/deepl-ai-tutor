"""Unit tests for LangGraph tutor graph nodes.

Each test exercises one node in isolation using a mock LLM so no real API
calls are made.  The pattern mirrors test_graph_chromadb.py: monkeypatch
graph._get_llm and (where relevant) graph._retrieve_context.
"""
from __future__ import annotations

from dataclasses import asdict

from backend.interactive_tutor import graph


class _MockLLM:
    """Returns a fixed response for every generate() call."""

    def __init__(self, response):
        self.response = response
        self.calls: list[dict] = []

    def generate(self, prompt, **kwargs):
        self.calls.append({"prompt": prompt, **kwargs})
        return self.response


# ---------------------------------------------------------------------------
# generate_diagnostic
# ---------------------------------------------------------------------------

def test_generate_diagnostic_populates_questions(monkeypatch):
    questions = [
        {"question_text": "What is X?", "options": ["A", "B", "C", "D"], "correct_index": 0},
        {"question_text": "What is Y?", "options": ["A", "B", "C", "D"], "correct_index": 1},
        {"question_text": "What is Z?", "options": ["A", "B", "C", "D"], "correct_index": 2},
    ]
    monkeypatch.setattr(graph, "_get_llm", lambda: _MockLLM({"questions": questions}))

    state: graph.GraphState = {
        "current_concept": "Photosynthesis",
        "concept_summary": "Plants convert light to energy.",
        "chat_history": [],
    }
    result = graph.generate_diagnostic(state)

    assert result["diagnostic_questions"] == questions
    assert result["diagnostic_score"] == 0.0
    assert result["presentation_depth"] == "intermediate"


def test_generate_diagnostic_handles_non_dict_response(monkeypatch):
    monkeypatch.setattr(graph, "_get_llm", lambda: _MockLLM("unexpected string"))

    state: graph.GraphState = {"current_concept": "Topic", "concept_summary": "", "chat_history": []}
    result = graph.generate_diagnostic(state)

    assert result["diagnostic_questions"] == []


# ---------------------------------------------------------------------------
# evaluate_diagnostic  (no LLM — pure arithmetic)
# ---------------------------------------------------------------------------

def test_evaluate_diagnostic_all_correct_gives_advanced():
    questions = [
        {"question_text": "Q1", "correct_index": 0},
        {"question_text": "Q2", "correct_index": 1},
        {"question_text": "Q3", "correct_index": 2},
    ]
    state: graph.GraphState = {
        "diagnostic_questions": questions,
        "diagnostic_answers": [0, 1, 2],
    }
    result = graph.evaluate_diagnostic(state)

    assert result["diagnostic_score"] == 1.0
    assert result["presentation_depth"] == "advanced"


def test_evaluate_diagnostic_none_correct_gives_beginner():
    questions = [{"correct_index": 0}, {"correct_index": 0}, {"correct_index": 0}]
    state: graph.GraphState = {
        "diagnostic_questions": questions,
        "diagnostic_answers": [1, 1, 1],
    }
    result = graph.evaluate_diagnostic(state)

    assert result["diagnostic_score"] == 0.0
    assert result["presentation_depth"] == "beginner"


def test_evaluate_diagnostic_partial_correct_gives_intermediate():
    questions = [{"correct_index": 0}, {"correct_index": 1}, {"correct_index": 2}]
    state: graph.GraphState = {
        "diagnostic_questions": questions,
        "diagnostic_answers": [0, 0, 0],  # 1 of 3 correct → ~0.33
    }
    result = graph.evaluate_diagnostic(state)

    assert result["presentation_depth"] == "beginner"  # 0.33 < 0.4


def test_evaluate_diagnostic_empty_questions():
    state: graph.GraphState = {"diagnostic_questions": [], "diagnostic_answers": []}
    result = graph.evaluate_diagnostic(state)

    assert result["diagnostic_score"] == 0.0
    assert result["presentation_depth"] == "intermediate"


# ---------------------------------------------------------------------------
# present_concept  — fast path (enriched_topic with audio_path already set)
# ---------------------------------------------------------------------------

def test_present_concept_fast_path_uses_content_md_directly():
    from backend.content.models import EnrichedTopic, Topic, Diagram

    topic = Topic(topic_id="t1", title="Photosynthesis", summary="S", source_section_ids=[], order=0)
    enriched = EnrichedTopic(
        topic=topic,
        content_md="# Photosynthesis\n\nPlants convert light.",
        key_takeaways=["Key 1"],
        diagrams=[Diagram(diagram_id="d1", diagram_type="mermaid", content="graph LR A-->B", caption="Flow")],
        inline_questions=[],
        top_concepts=["chlorophyll", "ATP"],
        audio_path="/fake/audio.mp3",
    )

    state: graph.GraphState = {
        "current_concept": "Photosynthesis",
        "presentation_depth": "intermediate",
        "enriched_topic": asdict(enriched),
        "concept_content": "",
        "module_id": "mod-1",
        "audio_enabled": False,
        "chat_history": [],
    }

    result = graph.present_concept(state)

    slide = next(m for m in result["chat_history"] if m.get("role") == "slide")
    assert slide["concept"] == "Photosynthesis"
    assert slide["transcript"] == enriched.content_md
    assert slide["mermaid_code"] == "graph LR A-->B"
    assert result["topic_top_concepts"] == ["chlorophyll", "ATP"]
    assert result["attempts"] == 0
    assert result["concept_mastered"] is False


# ---------------------------------------------------------------------------
# present_concept  — fallback path (no enriched, no ChromaDB)
# ---------------------------------------------------------------------------

def test_present_concept_fallback_calls_llm(monkeypatch):
    slide_dict = {
        "top_concepts": ["concept_a"],
        "transcript": "Here is the fallback explanation.",
        "mermaid_code": "",
    }
    monkeypatch.setattr(graph, "_get_llm", lambda: _MockLLM(slide_dict))
    monkeypatch.setattr(graph, "_retrieve_context", lambda *a, **kw: "")

    state: graph.GraphState = {
        "current_concept": "Entropy",
        "concept_summary": "Disorder in a system.",
        "presentation_depth": "beginner",
        "enriched_topic": None,
        "concept_content": "",
        "module_id": "mod-1",
        "audio_enabled": False,
        "chat_history": [],
    }

    result = graph.present_concept(state)

    slide = next(m for m in result["chat_history"] if m.get("role") == "slide")
    assert slide["transcript"] == "Here is the fallback explanation."
    assert result["concept_content"] == "Here is the fallback explanation."


# ---------------------------------------------------------------------------
# ask_question
# ---------------------------------------------------------------------------

def test_ask_question_adds_question_to_state(monkeypatch):
    q = {"question": "What drives photosynthesis?", "expected_answer": "Light", "misconceptions": []}
    monkeypatch.setattr(graph, "_get_llm", lambda: _MockLLM(q))

    state: graph.GraphState = {
        "current_concept": "Photosynthesis",
        "concept_content": "Plants use light.",
        "presentation_depth": "intermediate",
        "attempts": 0,
        "feedback": "",
        "chat_history": [],
    }
    result = graph.ask_question(state)

    assert result["current_question"]["question"] == q["question"]
    tutor_msgs = [m for m in result["chat_history"] if m.get("role") == "tutor"]
    assert any(q["question"] in m["content"] for m in tutor_msgs)


# ---------------------------------------------------------------------------
# evaluate_response
# ---------------------------------------------------------------------------

def test_evaluate_response_correct_sets_mastered(monkeypatch):
    evaluation = {"is_correct": True, "feedback": "Well done!"}
    monkeypatch.setattr(graph, "_get_llm", lambda: _MockLLM(evaluation))

    state: graph.GraphState = {
        "current_question": {"question": "What is ATP?", "expected_answer": "Energy", "misconceptions": []},
        "student_answer": "ATP is the energy currency of cells.",
        "attempts": 0,
        "chat_history": [],
    }
    result = graph.evaluate_response(state)

    assert result["concept_mastered"] is True
    assert result["attempts"] == 1
    assert result["feedback"] == "Well done!"


def test_evaluate_response_incorrect_increments_attempts(monkeypatch):
    evaluation = {"is_correct": False, "feedback": "Not quite."}
    monkeypatch.setattr(graph, "_get_llm", lambda: _MockLLM(evaluation))

    state: graph.GraphState = {
        "current_question": {"question": "What is ATP?", "expected_answer": "Energy", "misconceptions": []},
        "student_answer": "I don't know.",
        "attempts": 1,
        "chat_history": [],
    }
    result = graph.evaluate_response(state)

    assert result["concept_mastered"] is False
    assert result["attempts"] == 2


def test_evaluate_response_appends_to_chat_history(monkeypatch):
    evaluation = {"is_correct": False, "feedback": "Try again."}
    monkeypatch.setattr(graph, "_get_llm", lambda: _MockLLM(evaluation))

    state: graph.GraphState = {
        "current_question": {"question": "Q?", "expected_answer": "A", "misconceptions": []},
        "student_answer": "wrong",
        "attempts": 0,
        "chat_history": [],
    }
    result = graph.evaluate_response(state)

    roles = [m["role"] for m in result["chat_history"]]
    assert "student" in roles
    assert "tutor" in roles


# ---------------------------------------------------------------------------
# simplify_foundations
# ---------------------------------------------------------------------------

def test_simplify_foundations_appends_explanation_and_resets_attempts(monkeypatch):
    monkeypatch.setattr(graph, "_get_llm", lambda: _MockLLM("Here is a simple breakdown."))

    state: graph.GraphState = {
        "current_concept": "Entropy",
        "concept_content": "Entropy is disorder.",
        "attempts": 3,
        "chat_history": [],
    }
    result = graph.simplify_foundations(state)

    assert result["attempts"] == 0
    assert any(
        "Let me break this down differently" in m.get("content", "")
        for m in result["chat_history"]
    )


# ---------------------------------------------------------------------------
# _advance_concept  (no LLM)
# ---------------------------------------------------------------------------

def test_advance_concept_moves_to_next():
    state: graph.GraphState = {
        "current_concept": "Photosynthesis",
        "remaining_concepts": ["Respiration", "Osmosis"],
        "mastered_concepts": [],
        "attempts": 2,
        "feedback": "old feedback",
        "current_question": {"question": "Q"},
        "diagnostic_questions": [{"q": 1}],
        "diagnostic_answers": [0],
        "enriched_topic": {"content_md": "x"},
        "topic_diagram": "graph",
        "topic_audio_path": "/audio.mp3",
        "topic_top_concepts": ["c1"],
    }
    result = graph._advance_concept(state)

    assert result["current_concept"] == "Respiration"
    assert result["remaining_concepts"] == ["Osmosis"]
    assert result["mastered_concepts"] == ["Photosynthesis"]
    assert result["concept_mastered"] is False
    assert result["attempts"] == 0
    assert result["current_question"] is None
    assert result["enriched_topic"] is None
    assert result["diagnostic_questions"] == []


def test_advance_concept_last_remaining_gives_empty_next():
    state: graph.GraphState = {
        "current_concept": "Photosynthesis",
        "remaining_concepts": [],
        "mastered_concepts": [],
        "attempts": 0,
        "feedback": "",
        "current_question": None,
        "diagnostic_questions": [],
        "diagnostic_answers": [],
        "enriched_topic": None,
        "topic_diagram": "",
        "topic_audio_path": "",
        "topic_top_concepts": [],
    }
    result = graph._advance_concept(state)

    assert result["current_concept"] == ""
    assert result["remaining_concepts"] == []
    assert result["mastered_concepts"] == ["Photosynthesis"]


# ---------------------------------------------------------------------------
# _session_complete  (no LLM)
# ---------------------------------------------------------------------------

def test_session_complete_appends_summary_and_adds_current_to_mastered():
    state: graph.GraphState = {
        "current_concept": "Osmosis",
        "mastered_concepts": ["Photosynthesis", "Respiration"],
        "chat_history": [],
    }
    result = graph._session_complete(state)

    assert "Osmosis" in result["mastered_concepts"]
    assert len(result["mastered_concepts"]) == 3
    summary = result["chat_history"][-1]["content"]
    assert "3 concept(s)" in summary
    assert "Osmosis" in summary
