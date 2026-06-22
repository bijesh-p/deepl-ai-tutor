# llm-eval-plan.md — LLM Evaluation Improvements

> **Goal:** Fix the LLM-eval data path so scores persist and display correctly under
> DeepEval 2.x, scope eval context properly, and add test coverage.
> **Spec:** [llm-eval-spec.md](llm-eval-spec.md) (§4 issues F1–F8).
> **Last updated:** 2026-06-22

This plan continues the phase numbering in [plan.md](plan.md) (latest committed: Phase 55).
[gui_plan.md](gui_plan.md) used Phases 56–61, so this plan uses **Phases 62+** to avoid
collisions. Each phase is one commit, committed via the `/git-commit` skill with a
`[Phase N] <desc>` message.

---

## Goal

1. Ensure DeepEval results actually persist under the pinned `deepeval>=2.0.0` (F1).
2. Make the observability dashboard accurate (no overwritten metric labels) and informative
   (F2, F5, F8).
3. Improve eval signal quality: concept-scoped faithfulness context and correct turn
   intent (F3, F4).
4. Add test coverage and a minimal run-status signal (F6, F7).

---

## Current state (verified)

- `deepeval>=2.0.0` pinned in [`pyproject.toml`](pyproject.toml).
- `_persist_results` reads `tr.metrics_metadata` / `md.metric` (1.x attribute names) in
  [`eval_runner.py`](backend/observability/eval_runner.py).
- Dashboard per-session row assigns `row[label]` per score in
  [`observability_page.py`](frontend/observability_page.py) (last-write-wins).
- `source_text` passed to the runner is all enriched topics concatenated in
  [`tutor_room.py`](frontend/tutor_room.py).
- No tests reference `eval_runner` / `run_session_evals_async`.

---

## Phases

### Phase 62 — Fix DeepEval 2.x result parsing + persistence (F1)

**Goal:** Scores from a real DeepEval 2.x run are correctly extracted and stored.

**Changes**
- [`backend/observability/eval_runner.py`](backend/observability/eval_runner.py)
  `_persist_results`: read `getattr(tr, "metrics_data", None) or getattr(tr, "metrics_metadata", [])`
  and `getattr(md, "name", None) or getattr(md, "metric", "unknown")`; keep `score`,
  `threshold`, `success`/`passed`, `reason` with the same fallbacks.
- Verify the installed DeepEval `TestResult` shape (inspect `deepeval.evaluate` return value)
  and align attribute names to the actual 2.x API.

**Files affected**
- `backend/observability/eval_runner.py`

**Definition of done**
- A synthetic `TestResult` (2.x shape) round-trips through `_persist_results` and yields
  non-empty `scores_json`.
- Full pytest suite passes.

---

### Phase 63 — Dashboard accuracy + metric descriptions (F2, F5, F8)

**Goal:** Per-session metrics are aggregated correctly and explained.

**Changes**
- [`backend/analytics/stats.py`](backend/analytics/stats.py) `get_eval_results` (or the page):
  aggregate multiple scores per metric per session into a mean (and pass-rate), instead of
  last-write-wins.
- [`frontend/observability_page.py`](frontend/observability_page.py): render the aggregated
  per-session values; add short descriptions for `AnswerRelevancyMetric`,
  `FaithfulnessMetric`, `ExplanationClarity`, and explain the 0.5 threshold.
- Optionally store a per-session aggregate in `scores_json` at write time (F5) for
  consistency between writer and reader.

**Files affected**
- `backend/analytics/stats.py`, `frontend/observability_page.py`,
  (optional) `backend/observability/eval_runner.py`

**Definition of done**
- A session with ≥ 2 cases per metric shows a single correct aggregated value per metric.
- Each metric has a one-line description and threshold help text in the UI.
- Full pytest suite passes.

---

### Phase 64 — Better eval signal: scoped context + turn intent + explicit Run Evals button (F3, F4, Q1)

**Goal:** Reduce noise/inflation in relevancy and faithfulness scores.

**Changes**
- [`frontend/tutor_room.py`](frontend/tutor_room.py) `_trigger_evals`: pass per-concept
  source text (a mapping concept → enriched `content_md`) instead of one concatenated blob.
- [`backend/observability/eval_runner.py`](backend/observability/eval_runner.py)
  `_build_test_cases`: use the current slide's concept content as `retrieval_context` for
  slide cases; classify tutor turns (question vs. feedback) and set a matching `input` intent
  rather than always `"Ask a question about: ..."`.

**Files affected**
- `frontend/tutor_room.py`, `backend/observability/eval_runner.py`

**Definition of done**
- Slide faithfulness uses concept-scoped context (verified in a unit test on
  `_build_test_cases`).
- Tutor-turn test cases carry an intent that matches their output type.
- Full pytest suite passes.

---

### Phase 65 — Test coverage + run-status signal (F6, F7)

**Goal:** Lock in the eval path with tests and surface a minimal status.

**Changes**
- New `tests/test_observability/test_eval_runner.py`: cover `_build_test_cases` (slide + Q&A,
  hint/simplify skipped, 10-cap), `LLMFactoryJudge.generate` with a stubbed factory,
  `_persist_results` with a synthetic result, and `get_eval_results` aggregation.
- [`backend/observability/eval_runner.py`](backend/observability/eval_runner.py): record a
  lightweight last-run status (timestamp, case count, error string) — e.g., a small
  `eval_runs` row or a value reused by the dashboard.
- [`frontend/observability_page.py`](frontend/observability_page.py): show "last eval run"
  status (ran / no cases / failed) so silent failures are visible.

**Files affected**
- `tests/test_observability/test_eval_runner.py` (new),
  `backend/observability/eval_runner.py`, `frontend/observability_page.py`

**Definition of done**
- New tests pass and cover the four target functions.
- The observability page shows a last-run status line.
- Full pytest suite passes.

---

## Open questions
- Should evals stay automatic at session end, or move behind an explicit "Run evals" button
  to control cost?
- Should average-score display be gated by a minimum cohort/session count to avoid noisy means?
- Should per-session aggregates be computed at write time, read time, or both?

---

## Commit convention

Format: `[Phase N] <short description>` — use the `/git-commit` skill after each phase.
