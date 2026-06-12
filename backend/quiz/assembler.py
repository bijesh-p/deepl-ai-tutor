from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone

from backend.quiz.models import Quiz, QuestionBank, QuizQuestion

_DIFFICULTY_ORDER = ["easy", "medium", "hard"]


def assemble_quiz(
    bank: QuestionBank,
    difficulty: str,
    num_questions: int = 10,
) -> Quiz:
    """Select and randomise questions from the bank for a quiz session.

    Falls back to adjacent difficulty levels if there are not enough
    questions at the requested level.
    """
    selected = _select_questions(bank.questions, difficulty, num_questions)

    random.shuffle(selected)

    return Quiz(
        quiz_id=str(uuid.uuid4()),
        module_id=bank.module_id,
        difficulty=difficulty,
        questions=selected,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _select_questions(
    questions: list[QuizQuestion],
    difficulty: str,
    n: int,
) -> list[QuizQuestion]:
    by_difficulty: dict[str, list[QuizQuestion]] = {d: [] for d in _DIFFICULTY_ORDER}
    for q in questions:
        if q.difficulty in by_difficulty:
            by_difficulty[q.difficulty].append(q)

    primary = list(by_difficulty.get(difficulty, []))
    random.shuffle(primary)
    selected = primary[:n]

    if len(selected) < n:
        # Fill from adjacent difficulties
        remaining = n - len(selected)
        others: list[QuizQuestion] = []
        for d in _DIFFICULTY_ORDER:
            if d != difficulty:
                others.extend(by_difficulty[d])
        random.shuffle(others)
        selected += others[:remaining]

    return selected
