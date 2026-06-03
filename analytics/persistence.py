from __future__ import annotations

import json
import uuid
import dataclasses

from analytics.db import get_db
from quiz.models import QuizResult


def save_user(user_id: str, username: str, db_path: str | None = None) -> None:
    """Insert a user row; silently ignore if the user already exists."""
    conn = get_db(db_path)
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
        (user_id, username),
    )
    conn.commit()
    conn.close()


def save_module(
    module_id: str,
    title: str,
    source_filename: str,
    db_path: str | None = None,
) -> None:
    """Insert a module row; silently ignore if it already exists."""
    conn = get_db(db_path)
    conn.execute(
        "INSERT OR IGNORE INTO modules (module_id, title, source_filename) VALUES (?, ?, ?)",
        (module_id, title, source_filename),
    )
    conn.commit()
    conn.close()


def save_attempt(result: QuizResult, difficulty: str, db_path: str | None = None) -> None:
    """Persist a completed QuizResult to the database."""
    answers_json = json.dumps([dataclasses.asdict(a) for a in result.answers])
    conn = get_db(db_path)
    conn.execute(
        """INSERT INTO quiz_attempts
           (attempt_id, quiz_id, module_id, user_id, difficulty,
            score, total, percentage, completed_at, answers_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            str(uuid.uuid4()),
            result.quiz_id,
            result.module_id,
            result.user_id,
            difficulty,
            result.score,
            result.total,
            result.percentage,
            result.completed_at,
            answers_json,
        ),
    )
    conn.commit()
    conn.close()


def get_user_attempts(
    user_id: str,
    module_id: str,
    db_path: str | None = None,
) -> list[dict]:
    """Return all quiz attempts for a user on a specific module, newest first."""
    conn = get_db(db_path)
    rows = conn.execute(
        """SELECT * FROM quiz_attempts
           WHERE user_id = ? AND module_id = ?
           ORDER BY completed_at DESC""",
        (user_id, module_id),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
