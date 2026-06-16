from __future__ import annotations

import os

import streamlit as st

from backend.analytics.db import get_db
from backend.analytics.stats import get_eval_results

_KNOWN_METRIC_LABELS = {
    "AnswerRelevancyMetric": "Answer Relevancy",
    "FaithfulnessMetric": "Faithfulness",
    "ExplanationClarity": "Explanation Clarity",
}


def render_observability_page() -> None:
    st.title("Observability Dashboard")

    _render_phoenix_section()
    st.markdown("---")
    _render_deepeval_section()
    st.markdown("---")

    if st.button("Back to Module Library", type="secondary"):
        st.session_state["page"] = "module_library"
        st.rerun()


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
            "Enable **Evals (DeepEval)** in the sidebar, then complete a tutor session "
            "to collect quality metrics here."
        )
        return

    import pandas as pd

    # ── Per-session table ────────────────────────────────────────────────────
    st.markdown(f"Showing your **{len(results)}** most recent session evaluation(s):")

    metric_names: list[str] = []
    rows = []
    for r in results:
        row: dict = {
            "Module": r["title"] or r["module_id"][:8],
            "Date": r["evaluated_at"][:10],
        }
        for s in r["scores"]:
            label = _KNOWN_METRIC_LABELS.get(s["metric"], s["metric"])
            if label not in metric_names:
                metric_names.append(label)
            val = s.get("score")
            passed = s.get("passed")
            if val is not None:
                badge = "✅" if passed else "❌"
                row[label] = f"{val:.2f} {badge}"
            else:
                row[label] = "—"
        rows.append(row)

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)

    # ── Average score bar chart ──────────────────────────────────────────────
    if metric_names:
        st.markdown("#### Average Scores")
        averages: dict[str, float] = {}
        counts: dict[str, int] = {}
        for r in results:
            for s in r["scores"]:
                label = _KNOWN_METRIC_LABELS.get(s["metric"], s["metric"])
                val = s.get("score")
                if val is not None:
                    averages[label] = averages.get(label, 0.0) + val
                    counts[label] = counts.get(label, 0) + 1
        avg_df = pd.DataFrame(
            {
                "Metric": list(averages.keys()),
                "Average Score": [
                    round(averages[k] / counts[k], 3) for k in averages
                ],
            }
        ).set_index("Metric")
        st.bar_chart(avg_df, y_label="Score (0–1)", use_container_width=True)
        st.caption("Scores range from 0 to 1. Threshold for pass is 0.5 for all metrics.")
