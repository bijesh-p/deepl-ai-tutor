import pytest
from datetime import timezone
from backend.quiz.evaluator import evaluate
from backend.quiz.models import Quiz, QuizQuestion


def _make_quiz() -> Quiz:
    questions = [
        QuizQuestion("q1", "What is 1+1?", "single_choice", ["1", "2", "3", "4"], [1], "2", "remember", "t1"),
        QuizQuestion("q2", "Select even numbers.", "multiple_choice", ["1", "2", "3", "4"], [1, 3], "2 and 4", "apply", "t1"),
        QuizQuestion("q3", "What is the capital of France?", "single_choice", ["Berlin", "Paris", "Rome", "Madrid"], [1], "Paris.", "remember", "t1"),
    ]
    return Quiz("quiz-1", "mod-1", questions, "2026-01-01T00:00:00Z")


def test_perfect_score():
    quiz = _make_quiz()
    answers = {"q1": [1], "q2": [1, 3], "q3": [1]}
    result = evaluate(quiz, answers, "user-1")
    assert result.score == 3
    assert result.total == 3
    assert result.percentage == 100.0


def test_zero_score():
    quiz = _make_quiz()
    answers = {"q1": [0], "q2": [0], "q3": [0]}
    result = evaluate(quiz, answers, "user-1")
    assert result.score == 0
    assert result.percentage == 0.0


def test_partial_score():
    quiz = _make_quiz()
    answers = {"q1": [1], "q2": [0], "q3": [2]}
    result = evaluate(quiz, answers, "user-1")
    assert result.score == 1
    assert result.percentage == pytest.approx(33.3, abs=0.2)


def test_missing_answer_counts_wrong():
    quiz = _make_quiz()
    result = evaluate(quiz, {}, "user-1")
    assert result.score == 0


def test_answer_results_populated():
    quiz = _make_quiz()
    answers = {"q1": [1], "q2": [1, 3], "q3": [1]}
    result = evaluate(quiz, answers, "user-1")
    assert len(result.answers) == 3
    assert all(r.is_correct for r in result.answers)
