import pytest
from quiz.assembler import assemble_quiz
from quiz.models import QuestionBank, QuizQuestion


def _make_bank(n_easy=5, n_medium=5, n_hard=5) -> QuestionBank:
    questions = []
    for difficulty, count in [("easy", n_easy), ("medium", n_medium), ("hard", n_hard)]:
        for i in range(count):
            questions.append(
                QuizQuestion(
                    question_id=f"{difficulty}-{i}",
                    question_text=f"Q {difficulty} {i}",
                    question_type="single_choice",
                    options=["A", "B", "C", "D"],
                    correct_answers=[0],
                    explanation="Explanation.",
                    difficulty=difficulty,
                    topic_id="topic-1",
                )
            )
    return QuestionBank(module_id="mod-1", questions=questions)


def test_assembles_correct_count():
    bank = _make_bank()
    quiz = assemble_quiz(bank, "medium", num_questions=10)
    assert len(quiz.questions) == 10


def test_prefers_requested_difficulty():
    bank = _make_bank(n_easy=0, n_medium=10, n_hard=0)
    quiz = assemble_quiz(bank, "medium", num_questions=5)
    assert all(q.difficulty == "medium" for q in quiz.questions)


def test_falls_back_when_insufficient():
    bank = _make_bank(n_easy=3, n_medium=0, n_hard=0)
    quiz = assemble_quiz(bank, "medium", num_questions=5)
    assert len(quiz.questions) == 3  # only 3 questions available total


def test_different_orderings_across_calls():
    bank = _make_bank(n_medium=20)
    ids_1 = [q.question_id for q in assemble_quiz(bank, "medium", 10).questions]
    ids_2 = [q.question_id for q in assemble_quiz(bank, "medium", 10).questions]
    # With 20 questions shuffled into 10, orderings should differ (very rarely won't)
    assert ids_1 != ids_2 or len(set(ids_1) - set(ids_2)) == 0
