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
        "SELECT module_id, title, source_filename, created_by, created_at, is_published FROM modules ORDER BY created_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def delete_module(module_id: str, db: sqlite3.Connection | None = None) -> None:
    """Delete a module and all its quiz attempts."""
    conn = db or get_db()
    conn.execute("DELETE FROM quiz_attempts WHERE module_id = ?", (module_id,))
    conn.execute("DELETE FROM modules WHERE module_id = ?", (module_id,))
    conn.commit()


def publish_module(
    module_id: str,
    db: sqlite3.Connection,
    shared_db: sqlite3.Connection,
) -> None:
    """Copy a module into the shared library and mark it as published."""
    row = load_module(module_id, db=db)
    if row is None:
        raise ValueError(f"Module {module_id} not found")

    shared_db.execute(
        """
        INSERT OR REPLACE INTO published_modules
            (module_id, title, source_filename, module_json, question_bank_json, created_by, published_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (
            row["module_id"],
            row["title"],
            row["source_filename"],
            row["module_json"],
            row["question_bank_json"],
            row["created_by"],
        ),
    )
    shared_db.commit()

    db.execute("UPDATE modules SET is_published = 1 WHERE module_id = ?", (module_id,))
    db.commit()


def unpublish_module(
    module_id: str,
    db: sqlite3.Connection,
    shared_db: sqlite3.Connection,
) -> None:
    """Remove a module from the shared library and clear its published flag."""
    shared_db.execute("DELETE FROM published_modules WHERE module_id = ?", (module_id,))
    shared_db.commit()

    db.execute("UPDATE modules SET is_published = 0 WHERE module_id = ?", (module_id,))
    db.commit()


def get_published_modules(shared_db: sqlite3.Connection) -> list[dict]:
    """Return all published modules ordered by publish date (newest first)."""
    rows = shared_db.execute(
        "SELECT module_id, title, source_filename, created_by, published_at "
        "FROM published_modules ORDER BY published_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def load_published_module(module_id: str, shared_db: sqlite3.Connection) -> dict | None:
    """Load raw JSON strings for a published module. Returns None if not found."""
    row = shared_db.execute(
        "SELECT * FROM published_modules WHERE module_id = ?", (module_id,)
    ).fetchone()
    return dict(row) if row else None


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


def load_user_profile(user_id: str, db: sqlite3.Connection | None = None) -> dict:
    """Return persisted profile for a user, or defaults if none exists."""
    conn = db or get_db()
    row = conn.execute(
        "SELECT * FROM user_profiles WHERE user_id = ?", (user_id,)
    ).fetchone()
    if row:
        d = dict(row)
        d["topic_mastery"] = json.loads(d.pop("topic_mastery_json", "{}"))
        d["module_visits"] = json.loads(d.pop("module_visits_json", "{}"))
        d["dark_mode"] = bool(d.get("dark_mode", 0))
        return d
    return {
        "user_id": user_id,
        "overall_depth": "intermediate",
        "topic_mastery": {},
        "module_visits": {},
        "last_seen": "",
        "llm_provider": "",
        "llm_model": "",
        "dark_mode": False,
    }


def save_dark_mode(user_id: str, dark_mode: bool, db: sqlite3.Connection | None = None) -> None:
    """Persist the dark-mode preference without touching mastery/depth fields."""
    conn = db or get_db()
    conn.execute(
        """
        INSERT INTO user_profiles (user_id, dark_mode)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET dark_mode = excluded.dark_mode
        """,
        (user_id, int(dark_mode)),
    )
    conn.commit()


def save_user_profile(
    user_id: str,
    overall_depth: str,
    topic_mastery: dict,
    module_id: str | None = None,
    llm_provider: str = "",
    llm_model: str = "",
    db: sqlite3.Connection | None = None,
) -> None:
    """Upsert the user profile, merging new mastery data with existing."""
    conn = db or get_db()

    # Load existing so we merge mastery and visits rather than overwrite
    existing = load_user_profile(user_id, db=conn)
    merged_mastery = {**existing["topic_mastery"], **topic_mastery}
    merged_visits = existing["module_visits"]
    if module_id:
        from datetime import datetime, timezone
        merged_visits[module_id] = datetime.now(timezone.utc).isoformat()

    # Keep existing llm prefs if caller doesn't supply new ones
    final_provider = llm_provider or existing.get("llm_provider", "")
    final_model = llm_model or existing.get("llm_model", "")

    conn.execute(
        """
        INSERT INTO user_profiles
            (user_id, overall_depth, topic_mastery_json, module_visits_json, last_seen, llm_provider, llm_model)
        VALUES (?, ?, ?, ?, datetime('now'), ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            overall_depth      = excluded.overall_depth,
            topic_mastery_json = excluded.topic_mastery_json,
            module_visits_json = excluded.module_visits_json,
            last_seen          = excluded.last_seen,
            llm_provider       = excluded.llm_provider,
            llm_model          = excluded.llm_model
        """,
        (user_id, overall_depth, json.dumps(merged_mastery), json.dumps(merged_visits),
         final_provider, final_model),
    )
    conn.commit()


def save_tutor_session(
    user_id: str,
    module_id: str,
    state: dict,
    phase: str,
    db: sqlite3.Connection | None = None,
) -> None:
    """Upsert the serialized tutor GraphState + UI phase for resume support."""
    conn = db or get_db()
    conn.execute(
        """
        INSERT INTO tutor_sessions (user_id, module_id, state_json, phase, updated_at)
        VALUES (?, ?, ?, ?, datetime('now'))
        ON CONFLICT(user_id, module_id) DO UPDATE SET
            state_json = excluded.state_json,
            phase      = excluded.phase,
            updated_at = excluded.updated_at
        """,
        (user_id, module_id, json.dumps(state), phase),
    )
    conn.commit()


def load_tutor_session(
    user_id: str,
    module_id: str,
    db: sqlite3.Connection | None = None,
) -> dict | None:
    """Return {"state": ..., "phase": ..., "updated_at": ...} for a saved session, or None."""
    conn = db or get_db()
    row = conn.execute(
        "SELECT state_json, phase, updated_at FROM tutor_sessions WHERE user_id = ? AND module_id = ?",
        (user_id, module_id),
    ).fetchone()
    if row is None:
        return None
    return {
        "state": json.loads(row["state_json"]),
        "phase": row["phase"],
        "updated_at": row["updated_at"],
    }


def delete_tutor_session(
    user_id: str,
    module_id: str,
    db: sqlite3.Connection | None = None,
) -> None:
    """Remove a saved tutor session (called once a session completes or ends)."""
    conn = db or get_db()
    conn.execute(
        "DELETE FROM tutor_sessions WHERE user_id = ? AND module_id = ?",
        (user_id, module_id),
    )
    conn.commit()


def save_topic_mastery(
    user_id: str,
    module_id: str,
    topic_id: str,
    mastered: bool,
    difficulty: str,
    attempts: int,
    db: sqlite3.Connection | None = None,
) -> None:
    """Upsert per-topic mastery status for a user/module."""
    conn = db or get_db()
    conn.execute(
        """
        INSERT INTO topic_mastery (user_id, module_id, topic_id, mastered, difficulty, attempts, last_updated)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(user_id, module_id, topic_id) DO UPDATE SET
            mastered     = excluded.mastered,
            difficulty   = excluded.difficulty,
            attempts     = excluded.attempts,
            last_updated = excluded.last_updated
        """,
        (user_id, module_id, topic_id, int(mastered), difficulty, attempts),
    )
    conn.commit()


def get_topic_mastery(
    user_id: str,
    module_id: str,
    db: sqlite3.Connection | None = None,
) -> list[dict]:
    """Return per-topic mastery rows for a user/module."""
    conn = db or get_db()
    rows = conn.execute(
        """
        SELECT topic_id, mastered, difficulty, attempts, last_updated
        FROM topic_mastery WHERE user_id = ? AND module_id = ?
        """,
        (user_id, module_id),
    ).fetchall()
    return [dict(r) for r in rows]
