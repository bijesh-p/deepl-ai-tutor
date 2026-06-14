from __future__ import annotations

import streamlit as st

from quiz.models import QuestionBank


def render_quiz_page(bank: QuestionBank) -> None:
    st.title("Quiz")

    # Stage 1: difficulty selection
    if "quiz" not in st.session_state:
        st.markdown("Choose a difficulty level, then start the quiz.")
        difficulty = st.radio(
            "Difficulty:", ["easy", "medium", "hard"], horizontal=True
        )
        if st.button("Start Quiz", type="primary"):
            from quiz.assembler import assemble_quiz
            quiz = assemble_quiz(bank, difficulty)
            st.session_state.quiz = quiz
            st.session_state.quiz_answers = {}
            st.rerun()

        st.divider()
        if st.button("← Back to Module"):
            st.session_state.page = "learn"
            st.rerun()
        return

    # Stage 2: answer questions
    quiz = st.session_state.quiz
    st.caption(f"Difficulty: {quiz.difficulty.capitalize()} · {len(quiz.questions)} questions")

    for i, q in enumerate(quiz.questions):
        st.markdown(f"**{i + 1}. {q.question_text}**")
        key = f"quiz_q_{q.question_id}"

        if q.question_type == "single_choice":
            choice = st.radio(
                "Select one:",
                q.options,
                key=key,
                index=None,
                label_visibility="collapsed",
            )
            if choice is not None:
                st.session_state.quiz_answers[q.question_id] = [q.options.index(choice)]
        else:
            selected: list[int] = []
            for j, opt in enumerate(q.options):
                if st.checkbox(opt, key=f"{key}_{j}"):
                    selected.append(j)
            st.session_state.quiz_answers[q.question_id] = selected

        st.markdown("")

    col1, col2 = st.columns([1, 6])
    with col1:
        if st.button("Submit Quiz", type="primary"):
            _submit_quiz(quiz)
    with col2:
        if st.button("Restart"):
            del st.session_state["quiz"]
            st.session_state.quiz_answers = {}
            st.rerun()


def _submit_quiz(quiz) -> None:
    from quiz.evaluator import evaluate
    from analytics.db import get_db
    from analytics.persistence import save_attempt
    from analytics.stats import get_module_stats

    result = evaluate(quiz, st.session_state.get("quiz_answers", {}))
    result.user_id = st.session_state.get("user_id", "")

    conn = get_db()
    save_attempt(result, conn)
    stats = get_module_stats(quiz.module_id, result.user_id, conn)
    conn.close()

    st.session_state.quiz_result = result
    st.session_state.module_stats = stats
    st.session_state.page = "results"
    del st.session_state["quiz"]
    st.rerun()
