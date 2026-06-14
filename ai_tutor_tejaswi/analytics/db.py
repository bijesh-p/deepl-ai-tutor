from __future__ import annotations
import os
import sqlite3


def get_db() -> sqlite3.Connection:
    db_path = os.environ.get("AI_TUTOR_DB_PATH", "data/ai_tutor.db")
    if db_path != ":memory:":
        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _create_tables(conn)
    return conn


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
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
    """)
    conn.commit()
