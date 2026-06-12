from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict

from backend.analytics.db import get_db
from backend.quiz.models import QuizResult


def save_user(
    username: str,
    db: sqlite3.Connection | None = None,
) -> str:
    """Upsert a user by username and return their user_id."""
    conn = db or get_db()
    row = conn.execute(
        "SELECT user_id FROM users WHERE username = ?", (username,)
    ).fetchone()
    if row:
        return row["user_id"]
    user_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO users (user_id, username) VALUES (?, ?)",
        (user_id, username),
    )
    conn.commit()
    return user_id


def save_module(
    module_id: str,
    title: str,
    source_filename: str,
    module_json: str,
    question_bank_json: str,
    created_by: str,
    db: sqlite3.Connection | None = None,
) -> None:
    """Persist a generated module with its full JSON blobs."""
    conn = db or get_db()
    conn.execute(
        """
        INSERT OR REPLACE INTO modules
            (module_id, title, source_filename, module_json, question_bank_json, created_by)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (module_id, title, source_filename, module_json, question_bank_json, created_by),
    )
    conn.commit()


def load_module(module_id: str, db: sqlite3.Connection | None = None) -> dict | None:
    """Load raw JSON strings for a module. Returns None if not found."""
    conn = db or get_db()
    row = conn.execute(
        "SELECT * FROM modules WHERE module_id = ?", (module_id,)
    ).fetchone()
    return dict(row) if row else None


def list_modules(db: sqlite3.Connection | None = None) -> list[dict]:
    """Return all modules ordered by creation date (newest first)."""
    conn = db or get_db()
    rows = conn.execute(
        "SELECT module_id, title, source_filename, created_by, created_at FROM modules ORDER BY created_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def delete_module(module_id: str, db: sqlite3.Connection | None = None) -> None:
    """Delete a module and all its quiz attempts."""
    conn = db or get_db()
    conn.execute("DELETE FROM quiz_attempts WHERE module_id = ?", (module_id,))
    conn.execute("DELETE FROM modules WHERE module_id = ?", (module_id,))
    conn.commit()


def save_attempt(
    result: QuizResult,
    difficulty: str,
    db: sqlite3.Connection | None = None,
) -> None:
    conn = db or get_db()
    answers_json = json.dumps([asdict(a) for a in result.answers])
    conn.execute(
        """
        INSERT INTO quiz_attempts
            (attempt_id, quiz_id, module_id, user_id, difficulty,
             score, total, percentage, completed_at, answers_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
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


def get_user_attempts(
    user_id: str,
    module_id: str,
    db: sqlite3.Connection | None = None,
) -> list[dict]:
    conn = db or get_db()
    rows = conn.execute(
        """
        SELECT * FROM quiz_attempts
        WHERE user_id = ? AND module_id = ?
        ORDER BY completed_at DESC
        """,
        (user_id, module_id),
    ).fetchall()
    return [dict(r) for r in rows]
