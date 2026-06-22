"""Unit tests for the DeepEval eval runner path.

Covers _build_test_cases, LLMFactoryJudge.generate, _persist_results,
record_eval_run / get_last_eval_run, and get_eval_results aggregation.
No real LLM calls or DeepEval evaluate() are made.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from backend.observability.eval_runner import (
    LLMFactoryJudge,
    _build_test_cases,
    _looks_like_feedback,
    _persist_results,
    get_last_eval_run,
    record_eval_run,
)
from backend.analytics.stats import get_eval_results


# ---------------------------------------------------------------------------
# Helpers — synthetic DeepEval 2.x objects
# ---------------------------------------------------------------------------

@dataclass
class _FakeMetricData:
    name: str
    score: float
    threshold: float
    success: bool
    reason: str = ""


@dataclass
class _FakeTestResult:
    metrics_data: list[_FakeMetricData]
    success: bool = True


@dataclass
class _FakeEvalResult:
    test_results: list[_FakeTestResult]


class _PersistentDB:
    """Wraps an in-memory SQLite connection and ignores close() calls so the
    connection stays alive across multiple helper function calls in a test."""

    def __init__(self) -> None:
        self._conn = sqlite3.connect(":memory:")
        self._conn.row_factory = sqlite3.Row

    def close(self) -> None:
        pass  # intentionally a no-op so helpers don't destroy the in-memory db

    def __getattr__(self, name: str):
        return getattr(self._conn, name)


def _make_db() -> _PersistentDB:
    """Return an in-memory SQLite db whose close() is a no-op."""
    return _PersistentDB()


# ---------------------------------------------------------------------------
# _build_test_cases
# ---------------------------------------------------------------------------

SLIDE_MSG = {"role": "slide", "concept": "Transformers", "transcript": "Attention is all you need."}
QUESTION_MSG = {"role": "tutor", "content": "What is the key innovation of the Transformer model?"}
FEEDBACK_MSG = {"role": "tutor", "content": "Great answer! You correctly identified self-attention."}
HINT_MSG = {"role": "tutor", "content": "Hint: think about the attention mechanism."}
SIMPLIFY_MSG = {"role": "tutor", "content": "Let me break this down from the basics."}


def test_build_test_cases_slide_and_question():
    history = [SLIDE_MSG, QUESTION_MSG]
    cases = _build_test_cases(history, source_text="full blob")
    assert len(cases) == 2
    assert "Transformers" in cases[0].input
    assert "Transformers" in cases[1].input
    # question turn should NOT be labelled as feedback
    assert "question" in cases[1].input.lower()


def test_build_test_cases_feedback_classified():
    history = [SLIDE_MSG, FEEDBACK_MSG]
    cases = _build_test_cases(history, source_text="blob")
    assert len(cases) == 2
    assert "feedback" in cases[1].input.lower()


def test_build_test_cases_hint_and_simplify_skipped():
    history = [SLIDE_MSG, HINT_MSG, SIMPLIFY_MSG, QUESTION_MSG]
    cases = _build_test_cases(history, source_text="blob")
    # only slide + the question should appear; hint and simplify are skipped
    assert len(cases) == 2


def test_build_test_cases_cap_at_ten():
    # 1 slide + 11 tutor questions → must be capped at 10
    history = [SLIDE_MSG] + [QUESTION_MSG] * 11
    cases = _build_test_cases(history, source_text="blob")
    assert len(cases) == 10


def test_build_test_cases_concept_scoped_context():
    concept_context = {"Transformers": "scoped content for transformers"}
    history = [SLIDE_MSG]
    cases = _build_test_cases(history, source_text="full blob", concept_context=concept_context)
    assert cases[0].retrieval_context == ["scoped content for transformers"]


def test_build_test_cases_fallback_to_source_text():
    history = [SLIDE_MSG]
    cases = _build_test_cases(history, source_text="full blob", concept_context={"Other": "x"})
    assert cases[0].retrieval_context == ["full blob"]


def test_looks_like_feedback_true():
    assert _looks_like_feedback("Great answer! You nailed it.")
    assert _looks_like_feedback("Not quite — your answer was missing the key point.")


def test_looks_like_feedback_false():
    assert not _looks_like_feedback("What is the key innovation of the Transformer model?")


# ---------------------------------------------------------------------------
# LLMFactoryJudge.generate
# ---------------------------------------------------------------------------

def test_llm_factory_judge_generate(monkeypatch):
    mock_llm = MagicMock()
    mock_llm.generate.return_value = "judge response"

    mock_factory = MagicMock()
    mock_factory.create.return_value = mock_llm

    # LLMFactory is imported inside generate() from backend.core.llm_client
    with patch("backend.core.llm_client.LLMFactory", mock_factory):
        judge = LLMFactoryJudge(provider="anthropic", model="claude-test")
        result = judge.generate("Is this answer relevant?")

    assert result == "judge response"
    mock_factory.create.assert_called_once_with(provider="anthropic", model="claude-test")


def test_llm_factory_judge_generate_returns_empty_on_error(monkeypatch):
    # Patch the factory so it raises inside generate()
    mock_factory = MagicMock()
    mock_factory.create.side_effect = Exception("boom")
    with patch("backend.core.llm_client.LLMFactory", mock_factory):
        judge = LLMFactoryJudge(provider="anthropic")
        result = judge.generate("prompt")
    assert result == ""


def test_llm_factory_judge_get_model_name():
    judge = LLMFactoryJudge(provider="anthropic", model="claude-sonnet-4-6")
    assert judge.get_model_name() == "anthropic/claude-sonnet-4-6"
    assert judge.name == "anthropic/claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# _persist_results
# ---------------------------------------------------------------------------

def test_persist_results_2x_shape(monkeypatch):
    db = _make_db()
    fake_result = _FakeEvalResult(test_results=[
        _FakeTestResult(metrics_data=[
            _FakeMetricData(name="AnswerRelevancyMetric", score=0.8, threshold=0.5, success=True),
            _FakeMetricData(name="FaithfulnessMetric", score=0.6, threshold=0.5, success=True),
        ]),
    ])

    monkeypatch.setattr("backend.analytics.db.get_db", lambda *a, **kw: db)
    _persist_results(fake_result, user_id="u1", module_id="m1")

    rows = db.execute("SELECT scores_json FROM eval_results WHERE user_id='u1'").fetchall()
    assert len(rows) == 1
    scores = json.loads(rows[0]["scores_json"])
    assert len(scores) == 2
    assert scores[0]["metric"] == "AnswerRelevancyMetric"
    assert scores[0]["score"] == pytest.approx(0.8)
    assert scores[0]["passed"] is True


def test_persist_results_empty_metrics_data(monkeypatch):
    db = _make_db()
    fake_result = _FakeEvalResult(test_results=[
        _FakeTestResult(metrics_data=[]),
    ])

    monkeypatch.setattr("backend.analytics.db.get_db", lambda *a, **kw: db)
    _persist_results(fake_result, user_id="u2", module_id="m1")

    rows = db.execute("SELECT scores_json FROM eval_results WHERE user_id='u2'").fetchall()
    assert len(rows) == 1
    scores = json.loads(rows[0]["scores_json"])
    assert scores == []


# ---------------------------------------------------------------------------
# record_eval_run / get_last_eval_run
# ---------------------------------------------------------------------------

def test_record_and_get_last_eval_run(monkeypatch):
    db = _make_db()
    monkeypatch.setattr("backend.analytics.db.get_db", lambda *a, **kw: db)

    record_eval_run("u1", "m1", case_count=5)
    status = get_last_eval_run("u1")

    assert status is not None
    assert status["case_count"] == 5
    assert status["error"] is None
    assert "m1" == status["module_id"]


def test_record_eval_run_with_error(monkeypatch):
    db = _make_db()
    monkeypatch.setattr("backend.analytics.db.get_db", lambda *a, **kw: db)

    record_eval_run("u1", "m1", case_count=3, error="judge timeout")
    status = get_last_eval_run("u1")

    assert status["error"] == "judge timeout"


def test_get_last_eval_run_returns_none_when_empty(monkeypatch):
    db = _make_db()
    monkeypatch.setattr("backend.analytics.db.get_db", lambda *a, **kw: db)

    assert get_last_eval_run("nonexistent_user") is None


# ---------------------------------------------------------------------------
# get_eval_results aggregation
# ---------------------------------------------------------------------------

def test_get_eval_results_aggregation(monkeypatch):
    db = _make_db()
    # Create eval_results table and insert two test cases for the same session
    db.execute("""
        CREATE TABLE IF NOT EXISTS eval_results (
            result_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, module_id TEXT NOT NULL,
            scores_json TEXT NOT NULL, evaluated_at TEXT NOT NULL
        )
    """)
    scores = [
        {"metric": "AnswerRelevancyMetric", "score": 0.8, "threshold": 0.5, "passed": True, "reason": ""},
        {"metric": "AnswerRelevancyMetric", "score": 0.6, "threshold": 0.5, "passed": True, "reason": ""},
        {"metric": "FaithfulnessMetric", "score": 0.4, "threshold": 0.5, "passed": False, "reason": ""},
    ]
    db.execute(
        "INSERT INTO eval_results VALUES (?,?,?,?,?)",
        ("rid1", "u1", "m1", json.dumps(scores), "2026-06-22T10:00:00+00:00"),
    )
    # modules table not needed — LEFT JOIN returns NULL title which is fine
    db.execute("CREATE TABLE IF NOT EXISTS modules (module_id TEXT PRIMARY KEY, title TEXT)")
    db.commit()

    results = get_eval_results("u1", db=db)

    assert len(results) == 1
    agg = results[0]["aggregated"]

    ar = agg["AnswerRelevancyMetric"]
    assert ar["mean"] == pytest.approx(0.7, abs=0.001)
    assert ar["pass_rate"] == pytest.approx(1.0)
    assert ar["count"] == 2

    faith = agg["FaithfulnessMetric"]
    assert faith["mean"] == pytest.approx(0.4, abs=0.001)
    assert faith["pass_rate"] == pytest.approx(0.0)
    assert faith["count"] == 1

    # raw_scores must also be present
    assert len(results[0]["raw_scores"]) == 3
