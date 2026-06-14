"""DeepEval quality metrics for tutor sessions.

run_session_evals_async() is called from tutor_room._end_session() as a
fire-and-forget background thread — must not block the UI.
Results are stored in SQLite and visible in the Arize Phoenix UI.

The judge LLM is the same provider/model chosen in the sidebar, pulled
through LLMFactory — no separate API key or configuration needed.
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
    provider: str | None = None,
    model: str | None = None,
) -> None:
    """Kick off DeepEval evals in a background daemon thread."""
    t = threading.Thread(
        target=_run,
        args=(chat_history, source_text, user_id, module_id, provider, model),
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
    provider: str | None,
    model: str | None,
) -> None:
    try:
        from deepeval import evaluate
        from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric, GEval
        from deepeval.test_case import LLMTestCase, LLMTestCaseParams
    except ImportError:
        _log.warning("deepeval not installed — skipping evals")
        return

    test_cases = _build_test_cases(chat_history, source_text)
    if not test_cases:
        _log.info("No eval test cases built from session history")
        return

    judge = LLMFactoryJudge(provider=provider, model=model)

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
        results = evaluate(
            test_cases=test_cases,
            metrics=metrics,
            run_async=False,
            print_results=False,
        )
        _persist_results(results, user_id, module_id)
        _log.info("Eval complete — %d test cases, judge=%s", len(test_cases), judge.get_model_name())
    except Exception as exc:
        _log.warning("DeepEval evaluate() failed: %s", exc)


# ---------------------------------------------------------------------------
# Build test cases from chat history
# ---------------------------------------------------------------------------

def _build_test_cases(chat_history: list[dict], source_text: str) -> list[Any]:
    """Extract slide + Q&A turns from chat history into DeepEval LLMTestCase objects."""
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
            cases.append(
                LLMTestCase(
                    input=f"Explain the concept: {msg.get('concept', '')}",
                    actual_output=msg.get("transcript", ""),
                    retrieval_context=[source_text] if source_text else [],
                )
            )

        elif role == "tutor" and current_slide:
            content = msg.get("content", "")
            # Skip hints and simplifications — only eval substantive tutor turns
            if content and not content.startswith("Hint:") and not content.startswith("Let me break"):
                cases.append(
                    LLMTestCase(
                        input=f"Ask a question about: {current_slide.get('concept', '')}",
                        actual_output=content,
                        retrieval_context=[current_slide.get("transcript", "")],
                    )
                )

    return cases[:10]  # cap to limit judge LLM cost


# ---------------------------------------------------------------------------
# LLMFactory judge — proper DeepEvalBaseLLM subclass
# ---------------------------------------------------------------------------

class LLMFactoryJudge:
    """DeepEval judge that delegates to the project's LLMFactory.

    Uses whichever provider/model is active in the app (Anthropic, Portkey,
    or Ollama) — no separate eval API key needed. The provider and model are
    captured at construction time from the caller (tutor_room passes them
    from session_state before the background thread starts).
    """

    def __init__(self, provider: str | None = None, model: str | None = None) -> None:
        self._provider = provider or os.environ.get("AI_TUTOR_LLM_PROVIDER", "anthropic")
        self._model = model  # None → factory picks from env / defaults

    def load_model(self) -> "LLMFactoryJudge":
        return self

    def generate(self, prompt: str, *args, **kwargs) -> str:
        try:
            from backend.core.llm_client import LLMFactory
            kwargs_for_factory = {}
            if self._model:
                kwargs_for_factory["model"] = self._model
            llm = LLMFactory.create(provider=self._provider, **kwargs_for_factory)
            result = llm.generate(prompt=prompt)
            return result if isinstance(result, str) else str(result)
        except Exception as exc:
            _log.warning("Judge LLM call failed: %s", exc)
            return ""

    async def a_generate(self, prompt: str, *args, **kwargs) -> str:
        return self.generate(prompt)

    def get_model_name(self) -> str:
        model_part = self._model or "default"
        return f"{self._provider}/{model_part}"

    # DeepEval checks for this attribute on the model object
    @property
    def name(self) -> str:
        return self.get_model_name()


# ---------------------------------------------------------------------------
# Persist eval results to SQLite
# ---------------------------------------------------------------------------

def _persist_results(results: Any, user_id: str, module_id: str) -> None:
    """Write metric scores to the eval_results table."""
    try:
        from backend.analytics.db import get_db
        db = get_db()
        _ensure_eval_table(db)

        scores: list[dict] = []
        for tr in getattr(results, "test_results", []) or []:
            for md in getattr(tr, "metrics_metadata", []) or []:
                scores.append({
                    "metric": getattr(md, "metric", "unknown"),
                    "score": getattr(md, "score", None),
                    "threshold": getattr(md, "threshold", None),
                    "passed": getattr(md, "success", None),
                    "reason": getattr(md, "reason", ""),
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
