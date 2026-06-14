import pytest
from quiz.assembler import assemble_quiz
from quiz.models import QuestionBank, QuizQuestion


def _make_bank(n_easy=5, n_medium=5, n_hard=5) -> QuestionBank:
    questions: list[QuizQuestion] = []
    for diff, prefix, n in [("easy", "e", n_easy), ("medium", "m", n_medium), ("hard", "h", n_hard)]:
        for i in range(n):
            questions.append(QuizQuestion(
                question_id=f"{prefix}{i}",
                question_text=f"{diff} Q{i}",
                question_type="single_choice",
                options=["A", "B", "C", "D"],
                correct_answers=[0],
                explanation="A",
                difficulty=diff,
                topic_id="t1",
            ))
    return QuestionBank(module_id="mod1", questions=questions)


def test_exact_count():
    quiz = assemble_quiz(_make_bank(), "easy", 5)
    assert len(quiz.questions) == 5


def test_requested_difficulty_preferred():
    quiz = assemble_quiz(_make_bank(), "medium", 5)
    assert all(q.difficulty == "medium" for q in quiz.questions)


def test_fallback_when_insufficient_hard():
    bank = _make_bank(n_hard=2)
    quiz = assemble_quiz(bank, "hard", 10)
    assert len(quiz.questions) == 10


def test_no_duplicates():
    quiz = assemble_quiz(_make_bank(n_easy=10), "easy", 8)
    ids = [q.question_id for q in quiz.questions]
    assert len(ids) == len(set(ids))


def test_different_runs_shuffle():
    bank = _make_bank(n_easy=10)
    orders = [
        tuple(q.question_id for q in assemble_quiz(bank, "easy", 5).questions)
        for _ in range(10)
    ]
    assert len(set(orders)) > 1, "Expected some randomisation across 10 runs"
