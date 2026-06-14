from __future__ import annotations

import matplotlib.pyplot as plt
import streamlit as st

from analytics.models import ModuleStats
from quiz.models import QuizResult


def render_results_page(result: QuizResult, stats: ModuleStats) -> None:
    st.title("Results")

    # Score headline
    pct = result.percentage
    colour = "green" if pct >= 70 else "orange" if pct >= 50 else "red"
    st.markdown(
        f"<h2 style='color:{colour}'>You scored {result.score} / {result.total} ({pct:.1f}%)</h2>",
        unsafe_allow_html=True,
    )
    st.markdown(f"**Percentile rank:** {stats.user_percentile:.0f}th percentile "
                f"(based on {stats.total_attempts} attempt{'s' if stats.total_attempts != 1 else ''})")

    # Cohort chart
    _render_chart(stats)

    # Per-question breakdown
    st.divider()
    st.subheader("Question Breakdown")
    for i, ar in enumerate(result.answers):
        icon = "✅" if ar.is_correct else "❌"
        with st.expander(f"{icon} Question {i + 1}", expanded=not ar.is_correct):
            st.markdown(f"**Your answer indices:** {ar.selected}")
            st.markdown(f"**Correct indices:** {ar.correct}")
            st.info(ar.explanation)

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Retake Quiz", type="primary"):
            # Keep module and question_bank; reset quiz state
            for key in ("quiz_result", "module_stats", "quiz", "quiz_answers"):
                st.session_state.pop(key, None)
            st.session_state.page = "quiz"
            st.rerun()
    with col2:
        if st.button("Upload New Document"):
            for key in ("module", "question_bank", "quiz_result", "module_stats",
                        "quiz", "quiz_answers", "selected_topic"):
                st.session_state.pop(key, None)
            st.session_state.page = "upload"
            st.rerun()


def _render_chart(stats: ModuleStats) -> None:
    labels = ["Min", "Average", "Max", "You"]
    values = [stats.min_score, stats.avg_score, stats.max_score, stats.user_score]
    colors = ["#90caf9", "#90caf9", "#90caf9", "#ef5350"]

    fig, ax = plt.subplots(figsize=(5, 3.5))
    bars = ax.bar(labels, values, color=colors, width=0.5)
    ax.set_ylabel("Score (%)")
    ax.set_ylim(0, 110)
    ax.set_title("Your Score vs. Cohort")
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 1,
            f"{val:.1f}%",
            ha="center",
            va="bottom",
            fontsize=9,
        )
    ax.spines[["top", "right"]].set_visible(False)
    st.pyplot(fig)
    plt.close(fig)
