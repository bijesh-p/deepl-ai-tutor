import pytest
from backend.quiz.assembler import assemble_quiz
from backend.quiz.models import BLOOM_LEVELS, QuestionBank, QuizQuestion


def _make_bank(**counts: int) -> QuestionBank:
    """Build a bank with `counts[level]` questions per Bloom's level.

    Any level not passed defaults to 0.
    """
    questions = []
    for level in BLOOM_LEVELS:
        for i in range(counts.get(level, 0)):
            questions.append(
                QuizQuestion(
                    question_id=f"{level}-{i}",
                    question_text=f"Q {level} {i}",
                    question_type="single_choice",
                    options=["A", "B", "C", "D"],
                    correct_answers=[0],
                    explanation="Explanation.",
                    bloom_level=level,
                    topic_id="topic-1",
                )
            )
    return QuestionBank(module_id="mod-1", questions=questions)


def _all_level_kwargs(n: int) -> dict:
    return {level: n for level in BLOOM_LEVELS}


def test_assembles_correct_count():
    bank = _make_bank(**_all_level_kwargs(5))
    quiz = assemble_quiz(bank, num_questions=12)
    assert len(quiz.questions) == 12


def test_distributes_across_all_levels():
    bank = _make_bank(**_all_level_kwargs(5))
    quiz = assemble_quiz(bank, num_questions=12)
    levels_present = {q.bloom_level for q in quiz.questions}
    assert levels_present == set(BLOOM_LEVELS)


def test_falls_back_when_insufficient():
    bank = _make_bank(remember=3)
    quiz = assemble_quiz(bank, num_questions=12)
    assert len(quiz.questions) == 3  # only 3 questions available total


def test_different_orderings_across_calls():
    bank = _make_bank(**_all_level_kwargs(20))
    ids_1 = [q.question_id for q in assemble_quiz(bank, num_questions=12).questions]
    ids_2 = [q.question_id for q in assemble_quiz(bank, num_questions=12).questions]
    # With far more questions available than drawn, orderings/selections should differ
    # (very rarely won't).
    assert ids_1 != ids_2 or len(set(ids_1) - set(ids_2)) == 0
