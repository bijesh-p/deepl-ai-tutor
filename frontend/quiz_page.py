from __future__ import annotations

import streamlit as st
from backend.quiz.assembler import assemble_quiz
from backend.quiz.evaluator import evaluate
from backend.quiz.models import QuestionBank, QuizQuestion
from frontend.styles import question_card_html, page_header_html


_DIFFICULTY_META = {
    "easy":   ("🟢", "Easy",   "Foundational concepts and definitions",     "#F0FDF4", "#10B981", "#065F46"),
    "medium": ("🟡", "Medium", "Applied understanding and key relationships", "#FFFBEB", "#F59E0B", "#92400E"),
    "hard":   ("🔴", "Hard",   "Deep analysis and edge cases",               "#FEF2F2", "#EF4444", "#991B1B"),
}


# ── Answer persistence helpers ───────────────────────────────────────────────
# Streamlit deletes a widget's session-state key whenever the widget is NOT
# rendered. For a one-question-at-a-time quiz that means every navigation
# step would wipe the previous answer.
# Fix: keep a permanent "quiz_answers" dict (plain session state, not a widget
# key) and sync widget state to/from it on every render of a question.

def _restore_widget_state(q: QuizQuestion, ss: dict) -> None:
    """Pre-set widget keys from quiz_answers so selections survive navigation."""
    saved = ss.get("quiz_answers", {}).get(q.question_id)
    wk = f"quiz_q_{q.question_id}"

    if q.question_type == "single_choice":
        # Only set if the key was wiped (not currently rendered)
        if saved and wk not in ss:
            idx = saved[0]
            if 0 <= idx < len(q.options):
                ss[wk] = q.options[idx]
    else:
        if saved is not None:
            for j in range(len(q.options)):
                opt_key = f"{wk}_opt_{j}"
                if opt_key not in ss:
                    ss[opt_key] = (j in saved)


def _save_widget_state(q: QuizQuestion, ss: dict) -> None:
    """Persist current widget state into quiz_answers after rendering."""
    answers: dict = ss.setdefault("quiz_answers", {})
    wk = f"quiz_q_{q.question_id}"

    if q.question_type == "single_choice":
        val = ss.get(wk)
        if val is not None and val in q.options:
            answers[q.question_id] = [q.options.index(val)]
    else:
        selected = [j for j in range(len(q.options)) if ss.get(f"{wk}_opt_{j}")]
        if selected:
            answers[q.question_id] = selected
        elif q.question_id in answers:
            del answers[q.question_id]


def _is_answered(q: QuizQuestion, ss: dict) -> bool:
    return bool(ss.get("quiz_answers", {}).get(q.question_id))


def _dot_progress_html(questions: list[QuizQuestion], current_idx: int, ss: dict) -> str:
    dots = []
    for i, q in enumerate(questions):
        is_current = i == current_idx
        is_answered = _is_answered(q, ss)

        if is_current and is_answered:
            bg, color, label, glow = "#2563EB", "white", "✓", "box-shadow:0 0 0 4px rgba(37,99,235,0.22);"
        elif is_current:
            bg, color, label, glow = "#2563EB", "white", str(i + 1), "box-shadow:0 0 0 4px rgba(37,99,235,0.22);"
        elif is_answered:
            bg, color, label, glow = "#10B981", "white", "✓", ""
        else:
            bg, color, label, glow = "#E5E7EB", "#9CA3AF", str(i + 1), ""

        dots.append(
            f'<div style="width:28px;height:28px;border-radius:50%;background:{bg};color:{color};'
            f'font-size:10px;font-weight:700;display:flex;align-items:center;'
            f'justify-content:center;flex-shrink:0;{glow}">{label}</div>'
        )

    return (
        '<div style="display:flex;gap:5px;justify-content:center;'
        'align-items:center;padding:8px 0;flex-wrap:wrap;">'
        + "".join(dots) + "</div>"
    )


def _collect_answers(quiz) -> dict[str, list[int]]:
    return dict(st.session_state.get("quiz_answers", {}))


# ── Pages ────────────────────────────────────────────────────────────────────

def render_quiz_page(bank: QuestionBank) -> None:
    if "quiz" not in st.session_state:
        _render_difficulty_selector(bank)
        return
    _render_quiz_question()


def _render_difficulty_selector(bank: QuestionBank) -> None:
    st.markdown(
        page_header_html(
            "Module Quiz",
            "Test your understanding across all topics. Click a difficulty card to begin.",
            "🎯",
        ),
        unsafe_allow_html=True,
    )

    st.markdown("#### Select Difficulty")
    selected = st.session_state.get("_quiz_difficulty_pick", "medium")

    cols = st.columns(3)
    for col, (key, (icon, label, desc, bg, border, text)) in zip(cols, _DIFFICULTY_META.items()):
        is_selected = selected == key
        outline = f"box-shadow:0 0 0 3px {border};" if is_selected else ""
        opacity = "1" if is_selected else "0.72"
        scale = "transform:scale(1.03);" if is_selected else ""
        check = (
            f'<div style="font-size:11px;font-weight:700;color:{text};margin-top:8px;">✓ Selected</div>'
            if is_selected else ""
        )
        with col:
            st.markdown(
                f"""<div style="padding:22px 16px;background:{bg};border:2px solid {border};
  border-radius:16px;text-align:center;min-height:130px;opacity:{opacity};
  {outline}{scale}transition:all 0.2s ease;margin-bottom:6px;">
  <div style="font-size:2.2rem;margin-bottom:8px;">{icon}</div>
  <div style="font-weight:700;font-size:16px;color:{text};font-family:'Inter',sans-serif;">{label}</div>
  <div style="font-size:11.5px;color:#6B7280;margin-top:6px;line-height:1.4;">{desc}</div>
  {check}
</div>""",
                unsafe_allow_html=True,
            )
            if st.button(
                f"{'✓ ' if is_selected else ''}{label}",
                key=f"_diff_{key}",
                type="primary" if is_selected else "secondary",
                use_container_width=True,
            ):
                st.session_state["_quiz_difficulty_pick"] = key
                st.rerun()

    difficulty = st.session_state.get("_quiz_difficulty_pick", "medium")

    if bank and bank.questions:
        count = sum(1 for q in bank.questions if q.difficulty == difficulty)
        total = len(bank.questions)
        icon_d, label_d = _DIFFICULTY_META[difficulty][0], _DIFFICULTY_META[difficulty][1]
        st.caption(f"{icon_d} **{label_d}** selected · {count} of {total} questions · quiz draws up to 10.")

    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)

    if st.button("Start Quiz", type="primary"):
        st.session_state["quiz"] = assemble_quiz(bank, difficulty, num_questions=10)
        st.session_state["quiz_difficulty"] = difficulty
        st.session_state["quiz_current_idx"] = 0
        st.session_state["quiz_answers"] = {}
        st.session_state.pop("_quiz_difficulty_pick", None)
        st.rerun()


def _render_quiz_question() -> None:
    quiz = st.session_state["quiz"]
    difficulty = st.session_state.get("quiz_difficulty", "medium")
    questions = quiz.questions
    total_q = len(questions)
    ss = st.session_state

    if "quiz_current_idx" not in ss:
        ss["quiz_current_idx"] = 0
    idx = ss["quiz_current_idx"]
    q = questions[idx]

    # Restore any saved answer for this question into widget state BEFORE rendering
    _restore_widget_state(q, ss)

    answered_count = sum(1 for q2 in questions if _is_answered(q2, ss))
    is_last = idx == total_q - 1
    all_answered = answered_count == total_q

    diff_icon, diff_label, _, diff_bg, diff_border, diff_fg = _DIFFICULTY_META[difficulty]
    unanswered = total_q - answered_count

    # ── Compact header: title + badge + progress stats in one HTML block ──────
    st.markdown(
        f"<div style='display:flex;align-items:center;justify-content:space-between;"
        f"margin-bottom:6px;flex-wrap:wrap;gap:6px;'>"
        f"<h2 style='margin:0;font-size:1.3rem;font-weight:700;color:#1E1B4B;'>Quiz</h2>"
        f"<div style='display:flex;align-items:center;gap:10px;flex-wrap:wrap;'>"
        f"<span style='font-size:12px;color:#10B981;font-weight:600;'>✓ {answered_count}</span>"
        f"<span style='font-size:12px;color:#9CA3AF;'>{unanswered} left</span>"
        f"<span style='background:{diff_bg};color:{diff_fg};border:1px solid {diff_border};"
        f"padding:3px 10px;border-radius:999px;font-size:11px;font-weight:600;'>"
        f"{diff_icon} {diff_label}</span>"
        f"</div></div>"
        f"<div style='font-size:11px;color:#9CA3AF;margin-bottom:4px;'>"
        f"Question <b style='color:#1E1B4B;'>{idx + 1}</b> / {total_q}</div>",
        unsafe_allow_html=True,
    )
    st.progress((idx + 1) / total_q)

    # ── Dot navigator ─────────────────────────────────────────────────────────
    st.markdown(_dot_progress_html(questions, idx, ss), unsafe_allow_html=True)

    # ── Question card ─────────────────────────────────────────────────────────
    st.markdown(question_card_html(idx + 1, q.question_text, q.question_type), unsafe_allow_html=True)

    # ── Answer inputs (no extra border container — CSS cards handle styling) ──
    if q.question_type == "single_choice":
        st.radio(
            label="",
            options=q.options,
            index=None,
            key=f"quiz_q_{q.question_id}",
            label_visibility="collapsed",
        )
    else:
        st.caption("Select all that apply:")
        for j, opt in enumerate(q.options):
            st.checkbox(opt, key=f"quiz_q_{q.question_id}_opt_{j}")

    # Persist current widget state immediately after rendering
    _save_widget_state(q, ss)

    # Re-read answered count after saving (may have just answered this question)
    answered_count = sum(1 for q2 in questions if _is_answered(q2, ss))
    all_answered = answered_count == total_q

    # ── Prev / Next navigation row ────────────────────────────────────────────
    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    col_prev, col_mid, col_next = st.columns([1, 2, 1])

    with col_prev:
        if st.button("← Previous", use_container_width=True, key="_quiz_prev", disabled=(idx == 0)):
            ss["quiz_current_idx"] -= 1
            st.rerun()

    with col_mid:
        if not _is_answered(q, ss):
            hint_color, hint_text = "#F59E0B", "Select an answer"
        elif not is_last:
            hint_color, hint_text = "#10B981", "Answered — Next ›"
        elif all_answered:
            hint_color, hint_text = "#2563EB", "All done! Submit ↓"
        else:
            hint_color, hint_text = "#F59E0B", f"{answered_count}/{total_q} answered"
        st.markdown(
            f"<div style='text-align:center;font-size:12px;color:{hint_color};"
            f"padding-top:6px;font-weight:600;'>{hint_text}</div>",
            unsafe_allow_html=True,
        )

    with col_next:
        if st.button("Next →", type="primary", use_container_width=True, key="_quiz_next", disabled=is_last):
            ss["quiz_current_idx"] += 1
            st.rerun()

    # ── Persistent Submit button (always visible) ─────────────────────────────
    st.markdown(
        f"<div style='border-top:1px solid #E5E7EB;margin-top:10px;padding-top:10px;"
        f"font-size:11px;color:#9CA3AF;text-align:center;margin-bottom:6px;'>"
        f"{'All questions answered — ready to submit.' if all_answered else f'{answered_count} of {total_q} answered'}"
        f"</div>",
        unsafe_allow_html=True,
    )
    if st.button(
        "Submit Quiz" if all_answered else f"Submit Quiz  ({answered_count}/{total_q} answered)",
        type="primary",
        use_container_width=True,
        key="_quiz_submit",
    ):
        _submit_quiz(quiz)


def _submit_quiz(quiz) -> None:
    answers = _collect_answers(quiz)
    result = evaluate(quiz, answers, st.session_state["user_id"])

    from backend.analytics.db import get_db
    from backend.analytics.persistence import save_attempt
    db = get_db(st.session_state.get("db_path"))
    save_attempt(result, st.session_state["quiz_difficulty"], db=db)

    st.session_state["quiz_result"] = result
    st.session_state["quiz_questions_map"] = {q.question_id: q for q in quiz.questions}
    st.session_state["page"] = "results"
    del st.session_state["quiz"]
    st.session_state.pop("quiz_current_idx", None)
    st.session_state.pop("quiz_answers", None)
    st.rerun()
