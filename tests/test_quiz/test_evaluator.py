from __future__ import annotations

import pytest
from pathlib import Path
from datetime import datetime, timezone

from quiz.assembler import assemble_quiz
from quiz.evaluator import evaluate
from quiz.models import QuestionBank, QuizResult

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def bank() -> QuestionBank:
    return QuestionBank.from_json((FIXTURES / "sample_bank.json").read_text())


@pytest.fixture
def quiz(bank):
    return assemble_quiz(bank, "easy", num_questions=2)


def test_returns_quiz_result(quiz):
    answers = {q.question_id: q.correct_answers for q in quiz.questions}
    result = evaluate(quiz, answers, user_id="user-1")
    assert isinstance(result, QuizResult)


def test_all_correct(quiz):
    answers = {q.question_id: q.correct_answers for q in quiz.questions}
    result = evaluate(quiz, answers, user_id="user-1")
    assert result.score == result.total
    assert result.percentage == 100.0


def test_none_correct(quiz):
    # Pick a wrong answer for every question
    answers = {}
    for q in quiz.questions:
        wrong = [i for i in range(len(q.options)) if i not in q.correct_answers]
        answers[q.question_id] = [wrong[0]] if wrong else []
    result = evaluate(quiz, answers, user_id="user-1")
    assert result.score == 0
    assert result.percentage == 0.0


def test_partial_score(bank):
    quiz = assemble_quiz(bank, "easy", num_questions=2)
    q0, q1 = quiz.questions[0], quiz.questions[1]
    answers = {
        q0.question_id: q0.correct_answers,   # correct
        q1.question_id: [],                    # wrong (no selection)
    }
    result = evaluate(quiz, answers, user_id="user-1")
    assert result.score == 1
    assert result.percentage == 50.0


def test_single_choice_exact_match(bank):
    sc = next(q for q in bank.questions if q.question_type == "single_choice")
    from quiz.models import Quiz
    quiz = Quiz(
        quiz_id="q-1", module_id=bank.module_id,
        difficulty="easy", questions=[sc],
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    result = evaluate(quiz, {sc.question_id: sc.correct_answers}, user_id="u")
    assert result.answers[0].is_correct is True


def test_multiple_choice_requires_all_correct(bank):
    mc = next((q for q in bank.questions if q.question_type == "multiple_choice"), None)
    if mc is None:
        pytest.skip("No multiple_choice question in fixture")
    from quiz.models import Quiz
    quiz = Quiz(
        quiz_id="q-1", module_id=bank.module_id,
        difficulty="medium", questions=[mc],
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    # Submit only first correct answer (partial) → should be wrong
    partial = [mc.correct_answers[0]]
    result = evaluate(quiz, {mc.question_id: partial}, user_id="u")
    assert result.answers[0].is_correct is False


def test_answer_result_fields(quiz):
    answers = {q.question_id: q.correct_answers for q in quiz.questions}
    result = evaluate(quiz, answers, user_id="user-1")
    for ar in result.answers:
        assert ar.question_id
        assert isinstance(ar.is_correct, bool)
        assert ar.explanation


def test_user_id_in_result(quiz):
    answers = {q.question_id: [] for q in quiz.questions}
    result = evaluate(quiz, answers, user_id="alice")
    assert result.user_id == "alice"


def test_total_matches_question_count(quiz):
    answers = {}
    result = evaluate(quiz, answers, user_id="u")
    assert result.total == len(quiz.questions)
