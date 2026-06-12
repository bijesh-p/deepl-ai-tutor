from __future__ import annotations

from datetime import datetime, timezone

from backend.quiz.models import AnswerResult, Quiz, QuizResult


def evaluate(quiz: Quiz, user_answers: dict[str, list[int]], user_id: str) -> QuizResult:
    """Score user answers and return a QuizResult."""
    answer_results: list[AnswerResult] = []

    for question in quiz.questions:
        selected = user_answers.get(question.question_id, [])
        correct = question.correct_answers
        is_correct = sorted(selected) == sorted(correct)
        answer_results.append(
            AnswerResult(
                question_id=question.question_id,
                selected=selected,
                correct=correct,
                is_correct=is_correct,
                explanation=question.explanation,
            )
        )

    score = sum(1 for r in answer_results if r.is_correct)
    total = len(answer_results)
    percentage = round(score / total * 100, 1) if total else 0.0

    return QuizResult(
        quiz_id=quiz.quiz_id,
        module_id=quiz.module_id,
        user_id=user_id,
        score=score,
        total=total,
        percentage=percentage,
        answers=answer_results,
        completed_at=datetime.now(timezone.utc).isoformat(),
    )
