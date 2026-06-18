from __future__ import annotations

import os
import sqlite3
from pathlib import Path

_DEFAULT_DB = "data/ai_tutor.db"
_DEFAULT_DB_DIR = "data"
_DEFAULT_SHARED_DB = "data/shared/ai_tutor.db"


def db_path_for_user(username: str) -> str:
    """Return a per-user DB path: <AI_TUTOR_DB_DIR>/<username>/ai_tutor.db"""
    base = os.environ.get("AI_TUTOR_DB_DIR", _DEFAULT_DB_DIR)
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in username)
    return str(Path(base) / safe / "ai_tutor.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id    TEXT PRIMARY KEY,
    username   TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id             TEXT PRIMARY KEY REFERENCES users(user_id),
    overall_depth       TEXT NOT NULL DEFAULT 'intermediate',
    topic_mastery_json  TEXT NOT NULL DEFAULT '{}',
    module_visits_json  TEXT NOT NULL DEFAULT '{}',
    last_seen           TEXT NOT NULL DEFAULT (datetime('now')),
    llm_provider        TEXT NOT NULL DEFAULT '',
    llm_model           TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS modules (
    module_id          TEXT PRIMARY KEY,
    title              TEXT NOT NULL,
    source_filename    TEXT NOT NULL,
    module_json        TEXT NOT NULL DEFAULT '',
    question_bank_json TEXT NOT NULL DEFAULT '',
    created_by         TEXT NOT NULL DEFAULT '',
    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    is_published       INTEGER NOT NULL DEFAULT 0
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

CREATE TABLE IF NOT EXISTS tutor_sessions (
    user_id    TEXT NOT NULL REFERENCES users(user_id),
    module_id  TEXT NOT NULL,
    state_json TEXT NOT NULL,
    phase      TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, module_id)
);
"""

_MIGRATIONS = [
    "ALTER TABLE modules ADD COLUMN module_json TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE modules ADD COLUMN created_by TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE user_profiles ADD COLUMN llm_provider TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE user_profiles ADD COLUMN llm_model TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE modules ADD COLUMN is_published INTEGER NOT NULL DEFAULT 0",
]

_SHARED_SCHEMA = """
CREATE TABLE IF NOT EXISTS published_modules (
    module_id          TEXT PRIMARY KEY,
    title              TEXT NOT NULL,
    source_filename    TEXT NOT NULL,
    module_json        TEXT NOT NULL DEFAULT '',
    question_bank_json TEXT NOT NULL DEFAULT '',
    created_by         TEXT NOT NULL DEFAULT '',
    published_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


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


def get_shared_db(db_path: str | None = None) -> sqlite3.Connection:
    """Return a connection to the shared DB of admin-published modules."""
    path = db_path or os.environ.get("AI_TUTOR_SHARED_DB_PATH", _DEFAULT_SHARED_DB)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SHARED_SCHEMA)
    conn.commit()
    return conn
