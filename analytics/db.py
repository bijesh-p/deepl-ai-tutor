from __future__ import annotations

import os
import sqlite3

_DEFAULT_PATH = os.environ.get("AI_TUTOR_DB_PATH", "data/ai_tutor.db")

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id    TEXT PRIMARY KEY,
    username   TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS modules (
    module_id       TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    source_filename TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
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
"""


def get_db(path: str | None = None) -> sqlite3.Connection:
    """Return an open SQLite connection with all tables auto-created.

    Pass path=':memory:' in tests for an isolated in-memory database.
    The returned connection has row_factory set to sqlite3.Row for
    dict-like column access.
    """
    db_path = path or _DEFAULT_PATH
    if db_path != ":memory:":
        import pathlib
        pathlib.Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA_SQL)
    conn.commit()
    return conn
