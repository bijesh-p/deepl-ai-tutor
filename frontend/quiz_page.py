from __future__ import annotations

import streamlit as st

from analytics.persistence import save_attempt
from analytics.stats import get_module_stats
from quiz.assembler import assemble_quiz
from quiz.evaluator import evaluate
from quiz.models import QuestionBank


def render_quiz_page(bank: QuestionBank) -> None:
    st.title("Quiz")
    st.caption(f"Module: {st.session_state.get('module').title}")

    # Difficulty selector — shown only before quiz is assembled
    if "current_quiz" not in st.session_state:
        _render_difficulty_selector(bank)
        return

    _render_questions()


def _render_difficulty_selector(bank: QuestionBank) -> None:
    st.markdown("### Select Difficulty")

    counts = {"easy": 0, "medium": 0, "hard": 0}
    for q in bank.questions:
        counts[q.difficulty] = counts.get(q.difficulty, 0) + 1

    difficulty = st.radio(
        "Difficulty",
        options=["easy", "medium", "hard"],
        format_func=lambda d: f"{d.capitalize()} ({counts.get(d, 0)} questions available)",
        horizontal=True,
        label_visibility="collapsed",
    )

    num_q = st.slider("Number of questions", min_value=3, max_value=min(20, len(bank.questions)), value=min(10, len(bank.questions)))

    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("Start Quiz", type="primary"):
            quiz = assemble_quiz(bank, difficulty, num_questions=num_q)
            st.session_state["current_quiz"] = quiz
            st.session_state["quiz_answers"] = {}
            st.session_state["quiz_submitted"] = False
            st.rerun()
    with col2:
        if st.button("← Back to Module"):
            st.session_state["page"] = "learn"
            st.rerun()


def _render_questions() -> None:
    quiz = st.session_state["current_quiz"]
    answers: dict = st.session_state["quiz_answers"]
    submitted = st.session_state.get("quiz_submitted", False)

    if not submitted:
        st.markdown(f"**{len(quiz.questions)} questions · {quiz.difficulty.capitalize()} difficulty**")
        st.markdown("---")

    for i, q in enumerate(quiz.questions, 1):
        st.markdown(f"**Q{i}. {q.question_text}**")

        if q.question_type == "single_choice":
            options_display = ["(Select an answer)"] + q.options
            selection = st.radio(
                label=f"q{i}",
                options=options_display,
                index=0,
                key=f"quiz_q_{q.question_id}",
                label_visibility="collapsed",
                disabled=submitted,
            )
            if selection != "(Select an answer)":
                answers[q.question_id] = [q.options.index(selection)]
        else:
            selections = st.multiselect(
                label=f"q{i}",
                options=q.options,
                key=f"quiz_q_{q.question_id}",
                label_visibility="collapsed",
                disabled=submitted,
            )
            if selections:
                answers[q.question_id] = sorted(q.options.index(s) for s in selections)

        st.markdown("")

    st.markdown("---")

    if not submitted:
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("Submit Quiz", type="primary"):
                _submit_quiz(quiz, answers)
        with col2:
            if st.button("← Back"):
                del st.session_state["current_quiz"]
                st.rerun()
    else:
        if st.button("View Results →", type="primary"):
            st.session_state["page"] = "results"
            st.rerun()


def _submit_quiz(quiz, answers: dict) -> None:
    from frontend.demo_mode import is_demo
    user_id = st.session_state["user_id"]
    db_path = st.session_state["db_path"]

    result = evaluate(quiz, answers, user_id=user_id)

    if not is_demo():
        save_attempt(result, difficulty=quiz.difficulty, db_path=db_path)
        stats = get_module_stats(quiz.module_id, user_id, db_path=db_path)
    else:
        # Demo mode: compute stats without persisting to DB
        from analytics.models import ModuleStats
        stats = ModuleStats(
            module_id=quiz.module_id,
            total_attempts=1,
            min_score=result.percentage,
            max_score=result.percentage,
            avg_score=result.percentage,
            user_score=result.percentage,
            user_percentile=100.0,
            user_attempts=1,
        )

    st.session_state["quiz_result"] = result
    st.session_state["quiz_stats"] = stats
    st.session_state["quiz_submitted"] = True
    st.rerun()
