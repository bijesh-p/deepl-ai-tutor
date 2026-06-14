from datetime import datetime, timezone

from quiz.evaluator import evaluate
from quiz.models import Quiz, QuizQuestion


def _make_quiz(questions: list[QuizQuestion]) -> Quiz:
    return Quiz(
        quiz_id="q1",
        module_id="m1",
        difficulty="medium",
        questions=questions,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _q(qid: str, correct: list[int], qtype: str = "single_choice") -> QuizQuestion:
    return QuizQuestion(
        question_id=qid,
        question_text="Q?",
        question_type=qtype,
        options=["A", "B", "C", "D"],
        correct_answers=correct,
        explanation="Because.",
        difficulty="medium",
        topic_id="t1",
    )


def test_all_correct():
    quiz = _make_quiz([_q("q1", [0]), _q("q2", [1]), _q("q3", [2])])
    result = evaluate(quiz, {"q1": [0], "q2": [1], "q3": [2]})
    assert result.score == 3
    assert result.total == 3
    assert result.percentage == 100.0


def test_all_wrong():
    quiz = _make_quiz([_q("q1", [0]), _q("q2", [1])])
    result = evaluate(quiz, {"q1": [3], "q2": [3]})
    assert result.score == 0
    assert result.percentage == 0.0


def test_partial_score():
    quiz = _make_quiz([_q("q1", [0]), _q("q2", [1]), _q("q3", [2]), _q("q4", [3])])
    result = evaluate(quiz, {"q1": [0], "q2": [0], "q3": [2], "q4": [0]})
    assert result.score == 2
    assert result.percentage == 50.0


def test_unanswered_counts_as_wrong():
    quiz = _make_quiz([_q("q1", [0])])
    result = evaluate(quiz, {})
    assert result.score == 0
    assert result.answers[0].selected == []


def test_multiple_choice_correct():
    quiz = _make_quiz([_q("q1", [0, 2], qtype="multiple_choice")])
    result = evaluate(quiz, {"q1": [2, 0]})  # order should not matter
    assert result.answers[0].is_correct is True


def test_multiple_choice_partial_is_wrong():
    quiz = _make_quiz([_q("q1", [0, 2], qtype="multiple_choice")])
    result = evaluate(quiz, {"q1": [0]})
    assert result.answers[0].is_correct is False


def test_answer_result_fields():
    quiz = _make_quiz([_q("q1", [1])])
    result = evaluate(quiz, {"q1": [1]})
    ar = result.answers[0]
    assert ar.question_id == "q1"
    assert ar.correct == [1]
    assert ar.is_correct is True
