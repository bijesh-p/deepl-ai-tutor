from __future__ import annotations

import os

import streamlit as st

from backend.analytics.db import get_db
from backend.analytics.stats import get_eval_results
from frontend.nav import render_back_button

_KNOWN_METRIC_LABELS = {
    "AnswerRelevancyMetric": "Answer Relevancy",
    "FaithfulnessMetric": "Faithfulness",
    "ExplanationClarity": "Explanation Clarity",
}

_METRIC_DESCRIPTIONS = {
    "Answer Relevancy": (
        "Measures how relevant the tutor's response is to the student's question or prompt. "
        "A score ≥ 0.5 means the response stays on-topic."
    ),
    "Faithfulness": (
        "Checks whether the tutor's explanation is grounded in the source material and does not "
        "introduce unsupported claims. A score ≥ 0.5 means the content is factually faithful."
    ),
    "Explanation Clarity": (
        "Judges how clearly and conversationally the tutor explains concepts — using analogies "
        "and avoiding undefined jargon. A score ≥ 0.5 means the explanation is clear."
    ),
}


def render_observability_page() -> None:
    render_back_button("← Back to Module Library", "module_library", key="_back_observability")
    st.title("Observability Dashboard")

    _render_phoenix_section()
    st.markdown("---")
    _render_run_evals_button()
    st.markdown("---")
    _render_deepeval_section()


def _render_phoenix_section() -> None:
    st.markdown("### Trace Explorer (Arize Phoenix)")

    endpoint = os.environ.get(
        "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:6006/v1/traces"
    )
    base_url = endpoint.removesuffix("/v1/traces")

    st.markdown(
        f"Phoenix endpoint: `{base_url}`  \n"
        "Phoenix captures every LLM call, LangGraph node, and pipeline step as a named span."
    )
    st.link_button("Open Phoenix UI ↗", base_url)
    st.caption(
        "Start Phoenix with: `PYTHONPATH=. uv run phoenix serve`  \n"
        "Then open the link above to browse traces."
    )


def _render_run_evals_button() -> None:
    """Explicit button to trigger DeepEval quality metrics for the last completed session."""
    st.markdown("### Run Quality Evaluation")

    pending = st.session_state.get("pending_eval")
    if not pending:
        st.info(
            "No completed session available to evaluate.  \n"
            "Complete a tutor session first, then return here to run evals."
        )
        return

    module_id = pending.get("module_id", "")
    st.markdown(
        f"A completed session is ready to evaluate (module: `{module_id[:24] if module_id else '—'}`)."
    )
    st.caption(
        "Running evals calls the active LLM judge for each test case — this may incur API cost."
    )

    if st.button("Run Evals", type="primary"):
        try:
            from backend.observability.eval_runner import run_session_evals_async

            run_session_evals_async(
                chat_history=pending["chat_history"],
                source_text=pending["source_text"],
                user_id=pending["user_id"],
                module_id=pending["module_id"],
                provider=pending.get("provider"),
                model=pending.get("model"),
                db_path=pending.get("db_path"),
                concept_context=pending.get("concept_context"),
            )
            st.session_state.pop("pending_eval", None)
            st.success("Evals started in the background. Refresh this page in a moment to see results.")
        except Exception as exc:
            st.error(f"Failed to start evals: {exc}")


def _render_deepeval_section() -> None:
    st.markdown("### Quality Metrics (DeepEval)")

    user_id = st.session_state.get("user_id", "")
    db_path = st.session_state.get("db_path")

    if not user_id:
        st.warning("Not logged in.")
        return

    db = get_db(db_path)
    try:
        results = get_eval_results(user_id, db=db)
    finally:
        db.close()

    if not results:
        st.info(
            "No evaluation data yet.  \n"
            "Complete a tutor session, then click **Run Evals** on the Observability page "
            "to collect quality metrics here."
        )
        return

    import pandas as pd

    # ── Metric descriptions ──────────────────────────────────────────────────
    with st.expander("What do these metrics measure?", expanded=False):
        for label, desc in _METRIC_DESCRIPTIONS.items():
            st.markdown(f"**{label}** — {desc}")
        st.caption("Pass threshold: **0.5** for all metrics (scores range 0–1).")

    # ── Per-session aggregated table ─────────────────────────────────────────
    st.markdown(f"Showing your **{len(results)}** most recent session evaluation(s):")

    all_metric_labels: list[str] = []
    agg_rows = []
    for r in results:
        row: dict = {
            "Module": r["title"] or r["module_id"][:8],
            "Date": r["evaluated_at"][:10],
        }
        for metric_key, agg in r["aggregated"].items():
            label = _KNOWN_METRIC_LABELS.get(metric_key, metric_key)
            if label not in all_metric_labels:
                all_metric_labels.append(label)
            mean = agg.get("mean")
            pass_rate = agg.get("pass_rate")
            count = agg.get("count", 0)
            if mean is not None:
                badge = "✅" if (pass_rate is not None and pass_rate >= 0.5) else "❌"
                row[label] = f"{mean:.2f} {badge} ({count} cases)"
            else:
                row[label] = "—"
        agg_rows.append(row)

    agg_df = pd.DataFrame(agg_rows)
    st.dataframe(agg_df, use_container_width=True)
    st.caption(
        "Each cell shows the **mean score** across all test cases in the session, "
        "with ✅/❌ based on whether the mean pass-rate is ≥ 0.5."
    )

    # ── Raw per-turn scores in expander ─────────────────────────────────────
    with st.expander("Raw per-turn scores", expanded=False):
        for r in results:
            label = r["title"] or r["module_id"][:8]
            st.markdown(f"**{label}** — {r['evaluated_at'][:10]}")
            raw = r.get("raw_scores", [])
            if raw:
                raw_rows = []
                for s in raw:
                    metric_label = _KNOWN_METRIC_LABELS.get(s["metric"], s["metric"])
                    val = s.get("score")
                    passed = s.get("passed")
                    raw_rows.append({
                        "Metric": metric_label,
                        "Score": f"{val:.3f}" if val is not None else "—",
                        "Pass": "✅" if passed else "❌",
                        "Reason": (s.get("reason") or "")[:120],
                    })
                st.dataframe(pd.DataFrame(raw_rows), use_container_width=True, hide_index=True)
            else:
                st.caption("No raw score data.")
            st.markdown("---")

    # ── Average scores bar chart (across all sessions) ───────────────────────
    if all_metric_labels:
        st.markdown("#### Average Scores Across All Sessions")
        totals: dict[str, float] = {}
        counts: dict[str, int] = {}
        for r in results:
            for metric_key, agg in r["aggregated"].items():
                label = _KNOWN_METRIC_LABELS.get(metric_key, metric_key)
                mean = agg.get("mean")
                if mean is not None:
                    totals[label] = totals.get(label, 0.0) + mean
                    counts[label] = counts.get(label, 0) + 1
        avg_df = pd.DataFrame(
            {
                "Metric": list(totals.keys()),
                "Average Score": [round(totals[k] / counts[k], 3) for k in totals],
            }
        ).set_index("Metric")
        st.bar_chart(avg_df, y_label="Score (0–1)", use_container_width=True)
        st.caption("Scores range from 0 to 1. Pass threshold is 0.5 for all metrics.")
