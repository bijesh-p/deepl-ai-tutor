from __future__ import annotations

import streamlit as st
from backend.analytics.models import ModuleStats
from backend.analytics.stats import get_module_stats
from backend.analytics.db import get_db
from backend.quiz.models import QuizResult


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
    db = get_db(st.session_state.get("db_path"))
    stats = get_module_stats(result.module_id, result.user_id, db=db)
    _render_cohort_chart(stats)

    # Per-question breakdown
    quiz = st.session_state.get("quiz")
    quiz_questions = {q.question_id: q for q in quiz.questions} if quiz else {}

    st.markdown("---")
    st.markdown("### Question Breakdown")
    for i, ar in enumerate(result.answers):
        q = quiz_questions.get(ar.question_id)
        icon = "✅" if ar.is_correct else "❌"
        title = q.question_text if q else f"Question {i + 1}"
        if len(title) > 80:
            title = title[:77] + "..."
        with st.expander(f"{icon} {title}", expanded=not ar.is_correct):
            if q:
                for j, opt in enumerate(q.options):
                    is_correct = j in ar.correct
                    was_selected = j in ar.selected
                    if is_correct and was_selected:
                        st.markdown(f"✅ **{opt}**")
                    elif is_correct and not was_selected:
                        st.markdown(f"🟢 **{opt}**")
                    elif was_selected and not is_correct:
                        st.markdown(f"🔴 ~~{opt}~~")
                    else:
                        st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;{opt}")
            if ar.explanation:
                st.caption(f"💡 {ar.explanation}")

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
