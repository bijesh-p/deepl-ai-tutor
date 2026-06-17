from __future__ import annotations

import streamlit as st

from backend.analytics.db import get_db
from backend.analytics.models import CohortMastery, MasteryReport
from backend.analytics.stats import get_cohort_mastery, get_mastery_report


def render_mastery_report_page(module) -> None:
    st.title(f"Mastery Report — {module.title}")

    topic_order = [t.topic.title for t in module.topics]
    db = get_db(st.session_state.get("db_path"))
    report = get_mastery_report(module.module_id, st.session_state["user_id"], topic_order, db=db)
    cohort = get_cohort_mastery(module.module_id, topic_order, db=db)

    st.markdown(f"### You've mastered {report.mastered_count} / {report.total_count} topics")

    st.markdown("---")
    _render_topic_list(report)

    st.markdown("---")
    _render_cohort_chart(cohort)

    st.markdown("---")
    if st.button("Back to Module Library", type="secondary"):
        st.session_state["page"] = "module_library"
        st.rerun()


def _render_topic_list(report: MasteryReport) -> None:
    st.markdown("### Your Progress")
    for row in report.topics:
        if row.mastered:
            badge = "✅ Mastered"
        elif row.last_updated is not None:
            badge = "🔶 In progress"
        else:
            badge = "⬜ Not started"

        col_topic, col_status, col_difficulty, col_attempts = st.columns([3, 2, 2, 1])
        with col_topic:
            st.markdown(f"**{row.topic_id}**")
        with col_status:
            st.markdown(badge)
        with col_difficulty:
            st.markdown(f"Difficulty: {row.difficulty}")
        with col_attempts:
            st.markdown(f"Attempts: {row.attempts}")


def _render_cohort_chart(cohort: CohortMastery) -> None:
    st.markdown("### Cohort Comparison")

    if not any(t.total_users >= 2 for t in cohort.topics):
        st.info("Not enough cohort data yet.")
        return

    import pandas as pd

    data = pd.DataFrame(
        {
            "Topic": [t.topic_id for t in cohort.topics],
            "Mastered (%)": [t.mastered_pct for t in cohort.topics],
        }
    )
    st.bar_chart(data.set_index("Topic"))
