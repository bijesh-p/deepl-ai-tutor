from __future__ import annotations

import streamlit as st
from analytics.models import ModuleStats
from analytics.stats import get_module_stats
from analytics.db import get_db
from quiz.models import QuizResult


def render_results_page(result: QuizResult) -> None:
    st.title("Quiz Results")

    pct = result.percentage
    color = "green" if pct >= 70 else "orange" if pct >= 50 else "red"
    st.markdown(
        f"### You scored **{result.score} / {result.total}** "
        f"<span style='color:{color}'>({pct}%)</span>",
        unsafe_allow_html=True,
    )

    # Cohort stats
    db = get_db()
    stats = get_module_stats(result.module_id, result.user_id, db=db)
    _render_cohort_chart(stats)

    # Per-question breakdown
    st.markdown("---")
    st.markdown("### Question Breakdown")
    for i, ar in enumerate(result.answers):
        icon = "✅" if ar.is_correct else "❌"
        with st.expander(f"{icon} Question {i + 1}"):
            if ar.is_correct:
                st.success("Correct")
            else:
                st.error("Incorrect")
            st.markdown(f"**Explanation:** {ar.explanation}")

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Retake Quiz", type="secondary"):
            st.session_state["page"] = "quiz"
            for key in ["quiz", "quiz_answers", "quiz_result", "quiz_difficulty"]:
                st.session_state.pop(key, None)
            st.rerun()
    with col2:
        if st.button("Back to Module Library", type="secondary"):
            for key in ["module", "bank", "quiz", "quiz_answers", "quiz_result", "quiz_difficulty"]:
                st.session_state.pop(key, None)
            st.session_state["page"] = "module_library"
            st.rerun()


def _render_cohort_chart(stats: ModuleStats) -> None:
    if stats.total_attempts < 2:
        st.info("Complete more attempts to see cohort comparison.")
        return

    import pandas as pd

    data = pd.DataFrame(
        {
            "Metric": ["Your Score", "Average", "Minimum", "Maximum"],
            "Score (%)": [
                stats.user_score,
                stats.avg_score,
                stats.min_score,
                stats.max_score,
            ],
        }
    )

    st.markdown("### Cohort Comparison")
    st.bar_chart(data.set_index("Metric"))
    st.caption(
        f"Based on {stats.total_attempts} attempt(s). "
        f"You are in the **{stats.user_percentile:.0f}th percentile**. "
        f"You have attempted this quiz **{stats.user_attempts}** time(s)."
    )
