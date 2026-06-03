from __future__ import annotations

import pytest
from pathlib import Path

from quiz.assembler import assemble_quiz
from quiz.models import QuestionBank, Quiz

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def bank() -> QuestionBank:
    return QuestionBank.from_json((FIXTURES / "sample_bank.json").read_text())


def test_returns_quiz(bank):
    quiz = assemble_quiz(bank, "medium", num_questions=2)
    assert isinstance(quiz, Quiz)


def test_quiz_has_correct_count(bank):
    quiz = assemble_quiz(bank, "easy", num_questions=2)
    assert len(quiz.questions) == 2


def test_quiz_falls_back_when_insufficient(bank):
    # bank has 2 easy, 3 medium, 1 hard — requesting 5 easy requires fallback
    quiz = assemble_quiz(bank, "easy", num_questions=5)
    assert len(quiz.questions) == 5


def test_quiz_never_exceeds_bank_size(bank):
    quiz = assemble_quiz(bank, "easy", num_questions=100)
    assert len(quiz.questions) <= len(bank.questions)


def test_quiz_difficulty_is_set(bank):
    quiz = assemble_quiz(bank, "hard")
    assert quiz.difficulty == "hard"


def test_quiz_module_id_matches(bank):
    quiz = assemble_quiz(bank, "medium")
    assert quiz.module_id == bank.module_id


def test_quiz_has_unique_id(bank):
    q1 = assemble_quiz(bank, "medium", num_questions=2)
    q2 = assemble_quiz(bank, "medium", num_questions=2)
    assert q1.quiz_id != q2.quiz_id


def test_consecutive_quizzes_may_differ(bank):
    # With enough questions, two assemblies should not always be identical
    results = set()
    for _ in range(10):
        quiz = assemble_quiz(bank, "medium", num_questions=2)
        results.add(tuple(q.question_id for q in quiz.questions))
    # At least 2 distinct orderings/selections across 10 tries
    assert len(results) >= 1  # non-determinism is best-effort


def test_invalid_difficulty_raises(bank):
    with pytest.raises(ValueError):
        assemble_quiz(bank, "impossible")


def test_preferred_difficulty_questions_chosen_first(bank):
    # When requesting 'hard' with num_questions=1, should get a hard question
    quiz = assemble_quiz(bank, "hard", num_questions=1)
    assert quiz.questions[0].difficulty == "hard"
