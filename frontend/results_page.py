from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from analytics.models import ModuleStats
from quiz.models import QuizResult


def render_results_page(result: QuizResult, stats: ModuleStats) -> None:
    st.title("Quiz Results")

    _render_score_headline(result)
    st.markdown("---")
    _render_analytics_chart(result, stats)
    st.markdown("---")
    _render_answer_breakdown(result)
    st.markdown("---")
    _render_action_buttons()


def _render_score_headline(result: QuizResult) -> None:
    pct = result.percentage
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Your Score", f"{result.score} / {result.total}")
    with col2:
        st.metric("Percentage", f"{pct:.1f}%")
    with col3:
        if pct >= 80:
            grade, color = "Excellent", "🟢"
        elif pct >= 60:
            grade, color = "Good", "🟡"
        else:
            grade, color = "Needs Work", "🔴"
        st.metric("Grade", f"{color} {grade}")


def _render_analytics_chart(result: QuizResult, stats: ModuleStats) -> None:
    st.subheader("How You Compare")

    if stats.total_attempts <= 1:
        st.info("You are the first to attempt this module. Invite others to see cohort comparisons!")
        return

    pct_label = f"You: {stats.user_percentile:.0f}th percentile"
    st.caption(pct_label)

    fig = go.Figure()

    categories = ["Minimum", "Average", "Maximum", "You"]
    values = [stats.min_score, stats.avg_score, stats.max_score, stats.user_score]
    colors = ["#6c8ebf", "#82b366", "#82b366", "#d6a520"]

    fig.add_trace(
        go.Bar(
            x=categories,
            y=values,
            marker_color=colors,
            text=[f"{v:.1f}%" for v in values],
            textposition="outside",
        )
    )

    fig.update_layout(
        yaxis=dict(title="Score (%)", range=[0, 110]),
        xaxis_title="",
        showlegend=False,
        height=350,
        margin=dict(t=20, b=20),
    )

    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"Based on {stats.total_attempts} attempt(s) across all users.")


def _render_answer_breakdown(result: QuizResult) -> None:
    st.subheader("Question Breakdown")

    quiz = st.session_state.get("current_quiz")
    question_map = {q.question_id: q for q in quiz.questions} if quiz else {}

    for i, ar in enumerate(result.answers, 1):
        q = question_map.get(ar.question_id)
        question_text = q.question_text if q else f"Question {i}"
        icon = "✅" if ar.is_correct else "❌"

        with st.expander(f"{icon} Q{i}: {question_text}"):
            if q:
                # Show options with correct/selected highlighting
                for idx, option in enumerate(q.options):
                    is_correct_opt = idx in ar.correct
                    is_selected = idx in ar.selected
                    prefix = ""
                    if is_correct_opt and is_selected:
                        prefix = "✅ "
                    elif is_correct_opt:
                        prefix = "⬜ (correct) "
                    elif is_selected:
                        prefix = "❌ "
                    st.markdown(f"{prefix}{option}")

            st.info(f"**Explanation:** {ar.explanation}")


def _render_action_buttons() -> None:
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Retake Quiz", use_container_width=True):
            # Keep module and bank, reset quiz state
            for key in ["current_quiz", "quiz_answers", "quiz_submitted",
                        "quiz_result", "quiz_stats"]:
                st.session_state.pop(key, None)
            st.session_state["page"] = "quiz"
            st.rerun()
    with col2:
        if st.button("📄 Upload New Document", use_container_width=True):
            for key in ["module", "bank", "doc", "current_quiz", "quiz_answers",
                        "quiz_submitted", "quiz_result", "quiz_stats"]:
                st.session_state.pop(key, None)
            st.session_state["page"] = "upload"
            st.rerun()
