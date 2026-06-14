from __future__ import annotations
from datetime import datetime, timezone

from quiz.models import AnswerResult, Quiz, QuizResult


def evaluate(quiz: Quiz, user_answers: dict[str, list[int]]) -> QuizResult:
    results: list[AnswerResult] = []
    score = 0

    for q in quiz.questions:
        selected = user_answers.get(q.question_id, [])
        is_correct = sorted(selected) == sorted(q.correct_answers)
        if is_correct:
            score += 1
        results.append(
            AnswerResult(
                question_id=q.question_id,
                selected=selected,
                correct=q.correct_answers,
                is_correct=is_correct,
                explanation=q.explanation,
            )
        )

    total = len(quiz.questions)
    return QuizResult(
        quiz_id=quiz.quiz_id,
        module_id=quiz.module_id,
        user_id="",  # caller sets this
        score=score,
        total=total,
        percentage=round(score / total * 100, 1) if total else 0.0,
        answers=results,
        completed_at=datetime.now(timezone.utc).isoformat(),
    )
