from __future__ import annotations

import html
import streamlit as st
from backend.analytics.models import ModuleStats
from backend.analytics.stats import get_module_stats
from backend.analytics.db import get_db
from backend.quiz.models import QuizResult
from frontend.nav import render_back_button
from frontend.styles import score_banner_html

_LIBRARY_CLEAR_KEYS = ["module", "bank", "quiz", "quiz_answers", "quiz_result", "quiz_difficulty", "quiz_deadline", "quiz_timed_out"]


_DIFFICULTY_DISPLAY = {
    "easy":   ("🟢", "Easy",         "#F0FDF4", "#10B981", "#065F46"),
    "medium": ("🟡", "Intermediate", "#FFFBEB", "#F59E0B", "#92400E"),
    "hard":   ("🔴", "Hard",         "#FEF2F2", "#EF4444", "#991B1B"),
}


def render_results_page(result: QuizResult) -> None:
    render_back_button(
        "← Back to Library", "module_library", key="_back_results_top", clear_keys=_LIBRARY_CLEAR_KEYS
    )
    st.markdown("## Quiz Results")

    # This div has no background of its own — it sits directly on the
    # expander's background, which is dark in dark mode, so the text color
    # must follow the theme instead of being hardcoded to dark text.
    question_text_color = "#F1F5F9" if st.session_state.get("dark_mode", True) else "#111827"

    # ── Difficulty badge ──────────────────────────────────────────────────────
    difficulty = st.session_state.get("quiz_difficulty", "medium")
    d_icon, d_label, d_bg, d_border, d_fg = _DIFFICULTY_DISPLAY.get(
        difficulty, ("🟡", "Intermediate", "#FFFBEB", "#F59E0B", "#92400E")
    )
    st.markdown(
        f"<div style='text-align:center;margin-bottom:8px;'>"
        f"<span style='background:{d_bg};color:{d_fg};border:1px solid {d_border};"
        f"padding:4px 14px;border-radius:999px;font-size:13px;font-weight:600;'>"
        f"{d_icon} {d_label}</span></div>",
        unsafe_allow_html=True,
    )

    # ── Time's Up banner (if quiz was auto-submitted by timer) ──────────────
    timed_out = st.session_state.get("quiz_timed_out", False)
    if timed_out:
        st.markdown(
            "<div style='text-align:center;padding:12px 20px;background:#FEF2F2;"
            "border:2px solid #EF4444;border-radius:12px;margin-bottom:14px;'>"
            "<span style='font-size:1.4rem;'>⏱️</span> "
            "<span style='font-size:16px;font-weight:700;color:#991B1B;'>"
            "Time’s Up!</span>"
            "<div style='font-size:12px;color:#6B7280;margin-top:4px;'>"
            "The quiz was auto-submitted because the timer expired.</div></div>",
            unsafe_allow_html=True,
        )

    # ── Big score banner ──────────────────────────────────────────────────────
    st.markdown(
        score_banner_html(result.score, result.total, result.percentage, dark=st.session_state.get("dark_mode", True)),
        unsafe_allow_html=True,
    )

    # ── Cohort stats ──────────────────────────────────────────────────────────
    db = get_db(st.session_state.get("db_path"))
    stats = get_module_stats(result.module_id, result.user_id, db=db)
    _render_cohort_chart(stats)

    # ── Per-question breakdown ────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Question Breakdown")

    correct = sum(1 for ar in result.answers if ar.is_correct)
    not_answered = sum(1 for ar in result.answers if not ar.selected)
    wrong = len(result.answers) - correct - not_answered

    c1, c2, c3 = st.columns(3)
    c1.metric("Correct", f"{correct} ✅")
    c2.metric("Wrong", f"{wrong} ❌")
    c3.metric("Not Answered", f"{not_answered} ⚪")

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

    questions_map = st.session_state.get("quiz_questions_map", {})

    for i, ar in enumerate(result.answers):
        is_unanswered = not ar.selected
        if ar.is_correct:
            icon, border_color, bg_color, label = "✅", "#10B981", "#F0FDF4", "Correct"
        elif is_unanswered:
            icon, border_color, bg_color, label = "⚪", "#9CA3AF", "#F9FAFB", "Not Answered"
        else:
            icon, border_color, bg_color, label = "❌", "#EF4444", "#FEF2F2", "Incorrect"
        q = questions_map.get(ar.question_id)

        with st.expander(f"{icon} Question {i + 1}", expanded=True):
            # Question text
            if q:
                st.markdown(
                    f"<div style='font-weight:600;font-size:14px;color:{question_text_color};"
                    f"margin-bottom:10px;'>{q.question_text}</div>",
                    unsafe_allow_html=True,
                )

            # Result badge
            label_color = "#065F46" if ar.is_correct else "#991B1B"
            st.markdown(
                f"<div style='padding:6px 12px;background:{bg_color};border-left:3px solid {border_color};"
                f"border-radius:6px;margin-bottom:10px;display:inline-block;'>"
                f"<span style='font-weight:600;color:{label_color};'>{label}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

            # Options with correct/selected markers
            if q and q.options:
                opts_html = "<div style='display:flex;flex-direction:column;gap:6px;margin-bottom:10px;'>"
                for j, opt in enumerate(q.options):
                    is_correct_opt = j in ar.correct
                    is_selected_opt = j in ar.selected
                    if is_correct_opt and is_selected_opt:
                        opt_bg, opt_border, opt_color, marker = "#D1FAE5", "#10B981", "#065F46", "✅ Your answer (correct)"
                    elif is_correct_opt:
                        opt_bg, opt_border, opt_color, marker = "#D1FAE5", "#10B981", "#065F46", "✅ Correct answer"
                    elif is_selected_opt:
                        opt_bg, opt_border, opt_color, marker = "#FEE2E2", "#EF4444", "#991B1B", "❌ Your answer"
                    else:
                        opt_bg, opt_border, opt_color, marker = "#F9FAFB", "#E5E7EB", "#6B7280", ""
                    marker_html = (
                        f"<span style='font-size:10px;font-weight:600;color:{opt_color};"
                        f"margin-left:8px;white-space:nowrap;'>{marker}</span>"
                        if marker else ""
                    )
                    safe_opt = html.escape(opt)
                    opts_html += (
                        f"<div style='display:flex;align-items:center;padding:8px 12px;"
                        f"background:{opt_bg};border:1px solid {opt_border};border-radius:8px;'>"
                        f"<span style='font-size:13px;color:{opt_color};flex:1;'>{safe_opt}</span>"
                        f"{marker_html}</div>"
                    )
                opts_html += "</div>"
                st.markdown(opts_html, unsafe_allow_html=True)

            if ar.explanation:
                st.markdown(
                    f"<div style='padding:8px 12px;background:#F8FAFC;border:1px solid #E2E8F0;"
                    f"border-radius:6px;font-size:13px;color:#374151;'>"
                    f"<b style='color:#1E40AF;'>Explanation:</b> {ar.explanation}</div>",
                    unsafe_allow_html=True,
                )

    # ── Download report ───────────────────────────────────────────────────────
    st.markdown("---")
    lines = []
    lines.append(f"Quiz Results — {result.module_id}")
    lines.append(f"Score: {result.score} / {result.total} ({result.percentage}%)")
    raw_diff = st.session_state.get("quiz_difficulty", "medium")
    diff_display = _DIFFICULTY_DISPLAY.get(raw_diff, ("", raw_diff.capitalize()))[1]
    lines.append(f"Difficulty: {diff_display}")
    lines.append("")
    lines.append("--- Question Breakdown ---")
    for i, ar in enumerate(result.answers):
        q = questions_map.get(ar.question_id)
        status = "CORRECT" if ar.is_correct else ("NOT ANSWERED" if not ar.selected else "INCORRECT")
        q_text = q.question_text if q else f"Question {i + 1}"
        lines.append(f"\nQ{i + 1}. [{status}] {q_text}")
        if q and q.options:
            for j, opt in enumerate(q.options):
                if j in ar.correct and j in ar.selected:
                    marker = " ✓ (your correct answer)"
                elif j in ar.correct:
                    marker = " ✓ (correct answer)"
                elif j in ar.selected:
                    marker = " ✗ (your wrong answer)"
                else:
                    marker = ""
                lines.append(f"   {opt}{marker}")
        if ar.explanation:
            lines.append(f"   Explanation: {ar.explanation}")
    text_output = "\n".join(lines)
    st.download_button(
        label="📥 Download Results",
        data=text_output,
        file_name=f"quiz_results_{result.module_id}.txt",
        mime="text/plain",
        use_container_width=True,
    )

    # ── Actions ───────────────────────────────────────────────────────────────
    st.markdown("---")
    if st.button("🔄 Retake Quiz", type="secondary", use_container_width=True):
        st.session_state["page"] = "quiz"
        for key in ["quiz", "quiz_answers", "quiz_result", "quiz_difficulty", "quiz_deadline", "quiz_timed_out"]:
            st.session_state.pop(key, None)
        st.rerun()


def _render_cohort_chart(stats: ModuleStats) -> None:
    if stats.total_attempts < 2:
        st.info("Take more quiz attempts to unlock cohort comparison stats.")
        return

    import pandas as pd

    st.markdown("### How You Compare")

    # Percentile callout
    pct = stats.user_percentile
    pct_color = "#065F46" if pct >= 70 else "#92400E" if pct >= 40 else "#991B1B"
    st.markdown(
        f"""<div style="display:inline-block;padding:10px 20px;background:#F8FAFC;border:1px solid #E5E7EB;border-radius:10px;margin-bottom:12px;">
  <span style="font-size:1.5rem;font-weight:800;color:{pct_color};">{pct:.0f}<sup style="font-size:0.9rem;">th</sup></span>
  <span style="color:#6B7280;margin-left:6px;">percentile</span>
  &nbsp;·&nbsp;
  <span style="color:#9CA3AF;font-size:13px;">{stats.user_attempts} attempt(s) by you · {stats.total_attempts} total</span>
</div>""",
        unsafe_allow_html=True,
    )

    data = pd.DataFrame(
        {
            "Metric": ["You", "Average", "Min", "Max"],
            "Score (%)": [stats.user_score, stats.avg_score, stats.min_score, stats.max_score],
        }
    )
    st.bar_chart(data.set_index("Metric"), use_container_width=True, height=220)
