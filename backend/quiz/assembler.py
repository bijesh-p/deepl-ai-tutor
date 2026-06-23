from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone

from backend.quiz.models import BLOOM_LEVELS, Quiz, QuestionBank, QuizQuestion


def assemble_quiz(
    bank: QuestionBank,
    num_questions: int = 12,
) -> Quiz:
    """Select and randomise questions from the bank for a quiz session.

    Draws a mix across all six Bloom's taxonomy levels. Falls back to a
    pooled backfill across all levels if any level has too few questions.
    """
    selected = _select_questions(bank.questions, num_questions)

    random.shuffle(selected)

    return Quiz(
        quiz_id=str(uuid.uuid4()),
        module_id=bank.module_id,
        questions=selected,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _select_questions(
    questions: list[QuizQuestion],
    n: int,
) -> list[QuizQuestion]:
    by_level: dict[str, list[QuizQuestion]] = {level: [] for level in BLOOM_LEVELS}
    for q in questions:
        if q.bloom_level in by_level:
            by_level[q.bloom_level].append(q)

    base = n // len(BLOOM_LEVELS)
    remainder = n % len(BLOOM_LEVELS)
    bonus_levels = set(random.sample(BLOOM_LEVELS, remainder))

    selected: list[QuizQuestion] = []
    selected_ids: set[str] = set()
    for level in BLOOM_LEVELS:
        target = base + (1 if level in bonus_levels else 0)
        pool = list(by_level[level])
        random.shuffle(pool)
        for q in pool[:target]:
            selected.append(q)
            selected_ids.add(q.question_id)

    if len(selected) < n:
        # Fill shortfall from a pool of every not-yet-selected question,
        # regardless of level.
        remaining = n - len(selected)
        others = [q for q in questions if q.question_id not in selected_ids]
        random.shuffle(others)
        selected += others[:remaining]

    return selected
