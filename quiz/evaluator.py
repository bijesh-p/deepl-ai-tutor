from __future__ import annotations

from datetime import datetime, timezone

from quiz.models import AnswerResult, Quiz, QuizResult


def evaluate(quiz: Quiz, user_answers: dict[str, list[int]], user_id: str) -> QuizResult:
    """Score a completed quiz attempt.

    Args:
        quiz: The Quiz that was presented to the user.
        user_answers: Mapping of question_id → list of selected option indices.
        user_id: Identifier of the user taking the quiz.

    Returns:
        QuizResult with per-question breakdown and overall score.

    Scoring rules:
        - single_choice: correct if the single selected index matches the one correct answer.
        - multiple_choice: correct only if selected set exactly equals correct set (no extras, no omissions).
    """
    answer_results: list[AnswerResult] = []
    num_correct = 0

    for q in quiz.questions:
        selected = sorted(user_answers.get(q.question_id, []))
        correct = sorted(q.correct_answers)
        is_correct = selected == correct

        if is_correct:
            num_correct += 1

        answer_results.append(
            AnswerResult(
                question_id=q.question_id,
                selected=selected,
                correct=correct,
                is_correct=is_correct,
                explanation=q.explanation,
            )
        )

    total = len(quiz.questions)
    percentage = round((num_correct / total) * 100, 2) if total > 0 else 0.0

    return QuizResult(
        quiz_id=quiz.quiz_id,
        module_id=quiz.module_id,
        user_id=user_id,
        score=num_correct,
        total=total,
        percentage=percentage,
        answers=answer_results,
        completed_at=datetime.now(timezone.utc).isoformat(),
    )
