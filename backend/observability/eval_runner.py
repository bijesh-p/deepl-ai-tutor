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
    db_path: str | None = None,
    concept_context: dict[str, str] | None = None,
) -> None:
    """Kick off DeepEval evals in a background daemon thread.

    concept_context maps concept title → enriched content_md so each slide
    test case gets concept-scoped retrieval context instead of the full blob.
    source_text is kept for backwards compatibility when concept_context is absent.
    """
    t = threading.Thread(
        target=_run,
        args=(chat_history, source_text, user_id, module_id, provider, model, db_path, concept_context),
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
    db_path: str | None = None,
    concept_context: dict[str, str] | None = None,
) -> None:
    try:
        from deepeval import evaluate
        from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric, GEval
        from deepeval.test_case import LLMTestCase, LLMTestCaseParams
    except ImportError:
        _log.warning("deepeval not installed — skipping evals")
        return

    test_cases = _build_test_cases(chat_history, source_text, concept_context=concept_context)
    if not test_cases:
        _log.info("No eval test cases built from session history")
        record_eval_run(user_id, module_id, case_count=0, error="no test cases", db_path=db_path)
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
        _persist_results(results, user_id, module_id, db_path=db_path)
        record_eval_run(user_id, module_id, case_count=len(test_cases), db_path=db_path)
        _log.info("Eval complete — %d test cases, judge=%s", len(test_cases), judge.get_model_name())
    except Exception as exc:
        _log.warning("DeepEval evaluate() failed: %s", exc)
        record_eval_run(user_id, module_id, case_count=len(test_cases), error=str(exc), db_path=db_path)


# ---------------------------------------------------------------------------
# Build test cases from chat history
# ---------------------------------------------------------------------------

def _build_test_cases(
    chat_history: list[dict],
    source_text: str,
    concept_context: dict[str, str] | None = None,
) -> list[Any]:
    """Extract slide + Q&A turns from chat history into DeepEval LLMTestCase objects.

    concept_context maps concept title → enriched content_md.  When provided,
    each slide test case uses only that concept's content as retrieval_context
    instead of the full module blob (F3).  Tutor turns are classified as
    question or feedback so the input intent matches the output (F4).
    """
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
            concept = msg.get("concept", "")
            # Use concept-scoped content when available; fall back to full blob
            if concept_context and concept in concept_context:
                ctx = [concept_context[concept]]
            elif source_text:
                ctx = [source_text]
            else:
                ctx = []
            cases.append(
                LLMTestCase(
                    input=f"Explain the concept: {concept}",
                    actual_output=msg.get("transcript", ""),
                    retrieval_context=ctx,
                )
            )

        elif role == "tutor" and current_slide:
            content = msg.get("content", "")
            # Skip hints and simplifications — only eval substantive tutor turns
            if not content or content.startswith("Hint:") or content.startswith("Let me break"):
                continue
            concept = current_slide.get("concept", "")
            # Classify turn intent: feedback follows a student answer; a question is standalone
            is_feedback = msg.get("is_feedback", False) or _looks_like_feedback(content)
            if is_feedback:
                intent = f"Give feedback on the student's answer about: {concept}"
            else:
                intent = f"Ask a comprehension question about: {concept}"
            cases.append(
                LLMTestCase(
                    input=intent,
                    actual_output=content,
                    retrieval_context=[current_slide.get("transcript", "")],
                )
            )

    return cases[:10]  # cap to limit judge LLM cost


_FEEDBACK_PREFIXES = (
    "great", "good job", "well done", "correct", "that's right", "exactly",
    "not quite", "not exactly", "almost", "close", "actually", "unfortunately",
    "that's not", "incorrect", "you're right", "you're close",
)


def _looks_like_feedback(content: str) -> bool:
    """Heuristic: does this tutor turn read as answer feedback rather than a question?"""
    lower = content.lower().strip()
    return (
        any(lower.startswith(p) for p in _FEEDBACK_PREFIXES)
        or not content.rstrip().endswith("?")
        and any(kw in lower for kw in ("your answer", "you said", "you mentioned", "you wrote"))
    )


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

def _persist_results(results: Any, user_id: str, module_id: str, db_path: str | None = None) -> None:
    """Write metric scores to the eval_results table."""
    try:
        from backend.analytics.db import get_db
        db = get_db(db_path)
        _ensure_eval_table(db)

        scores: list[dict] = []
        for tr in getattr(results, "test_results", []) or []:
            # DeepEval 2.x uses metrics_data; 1.x used metrics_metadata
            md_list = getattr(tr, "metrics_data", None) or getattr(tr, "metrics_metadata", []) or []
            for md in md_list:
                scores.append({
                    "metric": getattr(md, "name", None) or getattr(md, "metric", "unknown"),
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


# ---------------------------------------------------------------------------
# Lightweight run-status record
# ---------------------------------------------------------------------------

def record_eval_run(
    user_id: str,
    module_id: str,
    case_count: int,
    error: str | None = None,
    db_path: str | None = None,
) -> None:
    """Write a lightweight status row so the dashboard can show last-run info."""
    try:
        from backend.analytics.db import get_db
        db = get_db(db_path)
        db.execute("""
            CREATE TABLE IF NOT EXISTS eval_runs (
                run_id      TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL,
                module_id   TEXT NOT NULL,
                case_count  INTEGER NOT NULL,
                error       TEXT,
                ran_at      TEXT NOT NULL
            )
        """)
        db.execute(
            """
            INSERT INTO eval_runs (run_id, user_id, module_id, case_count, error, ran_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                user_id,
                module_id,
                case_count,
                error,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        db.commit()
        db.close()
    except Exception as exc:
        _log.warning("Failed to record eval run status: %s", exc)


def get_last_eval_run(user_id: str, db_path: str | None = None) -> dict | None:
    """Return the most recent eval run status for a user, or None if none exists."""
    try:
        from backend.analytics.db import get_db
        db = get_db(db_path)
        db.execute("""
            CREATE TABLE IF NOT EXISTS eval_runs (
                run_id      TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL,
                module_id   TEXT NOT NULL,
                case_count  INTEGER NOT NULL,
                error       TEXT,
                ran_at      TEXT NOT NULL
            )
        """)
        row = db.execute(
            """
            SELECT module_id, case_count, error, ran_at
            FROM eval_runs WHERE user_id = ?
            ORDER BY ran_at DESC LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        db.close()
        if row is None:
            return None
        return {
            "module_id": row["module_id"],
            "case_count": row["case_count"],
            "error": row["error"],
            "ran_at": row["ran_at"],
        }
    except Exception as exc:
        _log.warning("Failed to read eval run status: %s", exc)
        return None
