from __future__ import annotations

import os
import sqlite3
from pathlib import Path

_DEFAULT_DB = "data/ai_tutor.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id    TEXT PRIMARY KEY,
    username   TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS modules (
    module_id          TEXT PRIMARY KEY,
    title              TEXT NOT NULL,
    source_filename    TEXT NOT NULL,
    module_json        TEXT NOT NULL DEFAULT '',
    question_bank_json TEXT NOT NULL DEFAULT '',
    created_by         TEXT NOT NULL DEFAULT '',
    created_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS quiz_attempts (
    attempt_id   TEXT PRIMARY KEY,
    quiz_id      TEXT NOT NULL,
    module_id    TEXT NOT NULL,
    user_id      TEXT NOT NULL REFERENCES users(user_id),
    difficulty   TEXT NOT NULL,
    score        INTEGER NOT NULL,
    total        INTEGER NOT NULL,
    percentage   REAL NOT NULL,
    completed_at TEXT NOT NULL,
    answers_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS topic_mastery (
    user_id      TEXT NOT NULL REFERENCES users(user_id),
    module_id    TEXT NOT NULL,
    topic_id     TEXT NOT NULL,
    mastered     INTEGER NOT NULL DEFAULT 0,
    difficulty   TEXT NOT NULL DEFAULT 'medium',
    attempts     INTEGER NOT NULL DEFAULT 0,
    last_updated TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, module_id, topic_id)
);
"""

_MIGRATIONS = [
    "ALTER TABLE modules ADD COLUMN module_json TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE modules ADD COLUMN created_by TEXT NOT NULL DEFAULT ''",
]


def get_db(db_path: str | None = None) -> sqlite3.Connection:
    """Return a SQLite connection, creating/migrating the schema on first call."""
    path = db_path or os.environ.get("AI_TUTOR_DB_PATH", _DEFAULT_DB)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    conn.commit()
    # Apply incremental migrations so existing DBs get new columns without data loss.
    for sql in _MIGRATIONS:
        try:
            conn.execute(sql)
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
    return conn
