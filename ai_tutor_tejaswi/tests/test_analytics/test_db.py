import sqlite3
from analytics.db import _create_tables


def test_tables_created(db_conn):
    tables = {
        row[0]
        for row in db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {"users", "modules", "quiz_attempts"} <= tables


def test_idempotent_create():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _create_tables(conn)
    _create_tables(conn)  # should not raise
    conn.close()


def test_users_unique_constraint(db_conn):
    db_conn.execute("INSERT INTO users (user_id, username) VALUES ('u1', 'alice')")
    db_conn.commit()
    import pytest
    with pytest.raises(Exception):
        db_conn.execute("INSERT INTO users (user_id, username) VALUES ('u2', 'alice')")
        db_conn.commit()
