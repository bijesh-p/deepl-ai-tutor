from __future__ import annotations
import dataclasses
import json
import sqlite3
import uuid

from analytics.db import get_db
from content.models import LearningModule
from quiz.models import QuizResult


def save_user(user_id: str, username: str, conn: sqlite3.Connection | None = None) -> str:
    """Insert user if not exists; return the effective user_id for that username."""
    owned = conn is None
    if owned:
        conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
        (user_id, username),
    )
    conn.commit()
    row = conn.execute(
        "SELECT user_id FROM users WHERE username = ?", (username,)
    ).fetchone()
    if owned:
        conn.close()
    return row["user_id"] if row else user_id


def save_module(
    module: LearningModule,
    source_filename: str = "",
    conn: sqlite3.Connection | None = None,
) -> None:
    owned = conn is None
    if owned:
        conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO modules (module_id, title, source_filename) VALUES (?, ?, ?)",
        (module.module_id, module.title, source_filename),
    )
    conn.commit()
    if owned:
        conn.close()


def save_attempt(result: QuizResult, conn: sqlite3.Connection | None = None) -> None:
    owned = conn is None
    if owned:
        conn = get_db()
    answers_json = json.dumps([dataclasses.asdict(a) for a in result.answers])
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
            "",  # difficulty stored per-attempt; enrich from Quiz if needed
            result.score,
            result.total,
            result.percentage,
            result.completed_at,
            answers_json,
        ),
    )
    conn.commit()
    if owned:
        conn.close()


def get_user_attempts(
    user_id: str,
    module_id: str,
    conn: sqlite3.Connection | None = None,
) -> list[dict]:
    owned = conn is None
    if owned:
        conn = get_db()
    rows = conn.execute(
        "SELECT * FROM quiz_attempts WHERE user_id = ? AND module_id = ? ORDER BY completed_at DESC",
        (user_id, module_id),
    ).fetchall()
    if owned:
        conn.close()
    return [dict(r) for r in rows]
