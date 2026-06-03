from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone

from quiz.difficulty import adjacent_levels, validate_difficulty
from quiz.models import Quiz, QuestionBank, QuizQuestion


def assemble_quiz(
    bank: QuestionBank,
    difficulty: str,
    num_questions: int = 10,
) -> Quiz:
    """Select and shuffle questions from the bank to form a Quiz.

    Filters by the requested difficulty first. If there are not enough
    questions at that level, fills from adjacent difficulty levels
    (nearest first). No LLM call — pure logic.

    Args:
        bank: The full question pool for a module.
        difficulty: Requested difficulty ('easy', 'medium', 'hard').
        num_questions: Target number of questions (default 10).

    Returns:
        A Quiz with randomly ordered questions.
    """
    difficulty = validate_difficulty(difficulty)
    by_level: dict[str, list[QuizQuestion]] = {"easy": [], "medium": [], "hard": []}
    for q in bank.questions:
        by_level[q.difficulty].append(q)

    selected: list[QuizQuestion] = []
    for level in adjacent_levels(difficulty):
        if len(selected) >= num_questions:
            break
        pool = by_level[level]
        need = num_questions - len(selected)
        selected.extend(random.sample(pool, min(need, len(pool))))

    random.shuffle(selected)

    return Quiz(
        quiz_id=str(uuid.uuid4()),
        module_id=bank.module_id,
        difficulty=difficulty,
        questions=selected,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
