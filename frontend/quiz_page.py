from __future__ import annotations

import streamlit as st
from backend.quiz.assembler import assemble_quiz
from backend.quiz.evaluator import evaluate
from backend.quiz.models import QuestionBank


def render_quiz_page(bank: QuestionBank) -> None:
    st.title("Quiz")

    if "quiz" not in st.session_state:
        difficulty = st.radio(
            "Select difficulty",
            options=["easy", "medium", "hard"],
            horizontal=True,
        )
        if st.button("Start Quiz", type="primary"):
            st.session_state["quiz"] = assemble_quiz(bank, difficulty, num_questions=10)
            st.session_state["quiz_difficulty"] = difficulty
            st.session_state["quiz_answers"] = {}
            st.rerun()
        return

    quiz = st.session_state["quiz"]
    answers: dict[str, list[int]] = st.session_state["quiz_answers"]

    st.caption(f"Difficulty: {st.session_state['quiz_difficulty'].capitalize()} — {len(quiz.questions)} questions")

    with st.form("quiz_form"):
        for i, q in enumerate(quiz.questions):
            st.markdown(f"**{i + 1}. {q.question_text}**")

            if q.question_type == "single_choice":
                choice = st.radio(
                    label="",
                    options=q.options,
                    index=None,
                    key=f"quiz_q_{q.question_id}",
                    label_visibility="collapsed",
                )
                if choice is not None:
                    answers[q.question_id] = [q.options.index(choice)]
            else:
                selected = []
                for j, opt in enumerate(q.options):
                    if st.checkbox(opt, key=f"quiz_q_{q.question_id}_opt_{j}"):
                        selected.append(j)
                answers[q.question_id] = selected

            st.markdown("")

        submitted = st.form_submit_button("Submit Quiz", type="primary")

    if submitted:
        result = evaluate(quiz, answers, st.session_state["user_id"])

        from backend.analytics.db import get_db
        from backend.analytics.persistence import save_attempt
        db = get_db(st.session_state.get("db_path"))
        save_attempt(result, st.session_state["quiz_difficulty"], db=db)

        st.session_state["quiz_result"] = result

        # Show per-question feedback before redirecting
        st.markdown("---")
        st.subheader("Your results")
        st.metric("Score", f"{result.score} / {result.total}")
        st.markdown("")

        for i, (q, r) in enumerate(zip(quiz.questions, result.answers)):
            icon = "✅" if r.is_correct else "❌"
            st.markdown(f"**{i + 1}. {icon} {q.question_text}**")
            for j, opt in enumerate(q.options):
                is_correct_opt = j in q.correct_answers
                was_selected = j in r.selected
                if is_correct_opt:
                    st.markdown(f"&nbsp;&nbsp;&nbsp;🟢 **{opt}** ← correct answer")
                elif was_selected:
                    st.markdown(f"&nbsp;&nbsp;&nbsp;🔴 {opt} ← your answer")
                else:
                    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{opt}")
            if r.explanation:
                st.caption(f"💡 {r.explanation}")
            st.markdown("")

        if st.button("See full results →", type="primary"):
            st.session_state["page"] = "results"
            del st.session_state["quiz"]
            st.rerun()
