"""DeepEval quality metrics for tutor sessions.

run_session_evals() is called from tutor_room._end_session() in a background
thread — it must not block the UI. Results are stored in SQLite and logged.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public entry point — non-blocking
# ---------------------------------------------------------------------------

def run_session_evals_async(
    chat_history: list[dict],
    source_text: str,
    user_id: str,
    module_id: str,
) -> None:
    """Kick off DeepEval evals in a background thread (fire-and-forget)."""
    t = threading.Thread(
        target=_run,
        args=(chat_history, source_text, user_id, module_id),
        daemon=True,
        name="eval-worker",
    )
    t.start()


# ---------------------------------------------------------------------------
# Core eval logic
# ---------------------------------------------------------------------------

def _run(
    chat_history: list[dict],
    source_text: str,
    user_id: str,
    module_id: str,
) -> None:
    try:
        from deepeval import evaluate
        from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric, GEval
        from deepeval.models.base_model import DeepEvalBaseLLM
        from deepeval.test_case import LLMTestCase, LLMTestCaseParams
    except ImportError:
        _log.warning("deepeval not installed — skipping evals")
        return

    test_cases = _build_test_cases(chat_history, source_text)
    if not test_cases:
        _log.info("No eval test cases built from session history")
        return

    judge = _AnthropicJudge()

    metrics = [
        AnswerRelevancyMetric(threshold=0.5, model=judge, async_mode=False),
        FaithfulnessMetric(threshold=0.5, model=judge, async_mode=False),
        GEval(
            name="ExplanationClarity",
            criteria=(
                "Does the tutor's explanation clearly and conversationally explain "
                "the concept, using analogies and avoiding jargon without definition?"
            ),
            evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=0.5,
            model=judge,
        ),
    ]

    try:
        results = evaluate(test_cases=test_cases, metrics=metrics, run_async=False, print_results=False)
        _persist_results(results, user_id, module_id)
        _log.info("Eval complete — %d test cases evaluated", len(test_cases))
    except Exception as exc:
        _log.warning("DeepEval evaluate() failed: %s", exc)


def _build_test_cases(chat_history: list[dict], source_text: str) -> list[Any]:
    """Extract slide + Q&A turns from chat history into DeepEval test cases."""
    try:
        from deepeval.test_case import LLMTestCase
    except ImportError:
        return []

    cases = []
    current_slide: dict | None = None

    for msg in chat_history:
        role = msg.get("role", "")

        if role == "slide":
            current_slide = msg
            # Eval: does the transcript explain the concept (topic as input)?
            cases.append(
                LLMTestCase(
                    input=f"Explain the concept: {msg.get('concept', '')}",
                    actual_output=msg.get("transcript", ""),
                    retrieval_context=[source_text] if source_text else [],
                )
            )

        elif role == "tutor" and current_slide:
            question_text = msg.get("content", "")
            if question_text and not question_text.startswith("Hint:") and not question_text.startswith("Let me break"):
                # Eval: is the tutor question relevant to the slide concept?
                cases.append(
                    LLMTestCase(
                        input=f"Ask a question about: {current_slide.get('concept', '')}",
                        actual_output=question_text,
                        retrieval_context=[current_slide.get("transcript", "")],
                    )
                )

    return cases[:10]  # cap at 10 to limit judge LLM cost


# ---------------------------------------------------------------------------
# Anthropic judge adapter for DeepEval
# ---------------------------------------------------------------------------

class _AnthropicJudge:
    """Minimal DeepEval LLM interface backed by our Anthropic LLMFactory."""

    def generate(self, prompt: str) -> str:
        try:
            from backend.core.llm_client import LLMFactory
            llm = LLMFactory.create()
            result = llm.generate(prompt=prompt)
            return result if isinstance(result, str) else str(result)
        except Exception as exc:
            _log.warning("Judge LLM call failed: %s", exc)
            return ""

    def get_model_name(self) -> str:
        return "anthropic-claude-judge"

    # DeepEval calls a_generate for async; fall back to sync
    async def a_generate(self, prompt: str) -> str:
        return self.generate(prompt)


# ---------------------------------------------------------------------------
# Persist eval results to SQLite
# ---------------------------------------------------------------------------

def _persist_results(results: Any, user_id: str, module_id: str) -> None:
    """Write eval metric scores to the eval_results table."""
    try:
        from backend.analytics.db import get_db
        db = get_db()
        _ensure_eval_table(db)

        scores: list[dict] = []
        # deepeval EvaluationResult has .test_results list
        for tr in getattr(results, "test_results", []) or []:
            for metric_data in getattr(tr, "metrics_metadata", []) or []:
                scores.append({
                    "metric": getattr(metric_data, "metric", "unknown"),
                    "score": getattr(metric_data, "score", None),
                    "threshold": getattr(metric_data, "threshold", None),
                    "passed": getattr(metric_data, "success", None),
                    "reason": getattr(metric_data, "reason", ""),
                })

        db.execute(
            """
            INSERT INTO eval_results
                (result_id, user_id, module_id, scores_json, evaluated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                user_id,
                module_id,
                json.dumps(scores),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        db.commit()
        db.close()
    except Exception as exc:
        _log.warning("Failed to persist eval results: %s", exc)


def _ensure_eval_table(db: sqlite3.Connection) -> None:
    db.execute("""
        CREATE TABLE IF NOT EXISTS eval_results (
            result_id    TEXT PRIMARY KEY,
            user_id      TEXT NOT NULL,
            module_id    TEXT NOT NULL,
            scores_json  TEXT NOT NULL,
            evaluated_at TEXT NOT NULL
        )
    """)
    db.commit()
