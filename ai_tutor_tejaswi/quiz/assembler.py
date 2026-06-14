from __future__ import annotations
import random
import uuid
from datetime import datetime, timezone

from quiz.models import QuestionBank, Quiz, QuizQuestion

_FALLBACK_ORDER = {
    "easy": ["easy", "medium", "hard"],
    "medium": ["medium", "easy", "hard"],
    "hard": ["hard", "medium", "easy"],
}


def assemble_quiz(
    bank: QuestionBank,
    difficulty: str,
    num_questions: int = 10,
) -> Quiz:
    pool: list[QuizQuestion] = []
    seen: set[str] = set()

    for diff in _FALLBACK_ORDER.get(difficulty, [difficulty]):
        if len(pool) >= num_questions:
            break
        candidates = [
            q for q in bank.questions if q.difficulty == diff and q.question_id not in seen
        ]
        random.shuffle(candidates)
        needed = num_questions - len(pool)
        pool.extend(candidates[:needed])
        seen.update(q.question_id for q in candidates[:needed])

    random.shuffle(pool)

    return Quiz(
        quiz_id=str(uuid.uuid4()),
        module_id=bank.module_id,
        difficulty=difficulty,
        questions=pool,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
