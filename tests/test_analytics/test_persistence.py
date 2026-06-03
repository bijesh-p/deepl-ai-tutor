from __future__ import annotations

import pytest
from datetime import datetime, timezone

from analytics.db import get_db
from analytics.persistence import get_user_attempts, save_attempt, save_module, save_user
from quiz.models import AnswerResult, QuizResult


def make_result(user_id: str, module_id: str, score: int, total: int) -> QuizResult:
    pct = round((score / total) * 100, 2)
    return QuizResult(
        quiz_id=f"quiz-{user_id}-{score}",
        module_id=module_id,
        user_id=user_id,
        score=score,
        total=total,
        percentage=pct,
        answers=[AnswerResult("q-1", [0], [0], True, "Because A.")],
        completed_at=datetime.now(timezone.utc).isoformat(),
    )


@pytest.fixture
def db(tmp_path) -> str:
    """Return path to a fresh temp SQLite file for each test."""
    return str(tmp_path / "test.db")


def test_save_and_retrieve_user(db):
    save_user("u-1", "alice", db_path=db)
    conn = get_db(db)
    row = conn.execute("SELECT username FROM users WHERE user_id='u-1'").fetchone()
    assert row["username"] == "alice"


def test_save_user_idempotent(db):
    save_user("u-1", "alice", db_path=db)
    save_user("u-1", "alice", db_path=db)  # should not raise
    conn = get_db(db)
    count = conn.execute("SELECT COUNT(*) FROM users WHERE user_id='u-1'").fetchone()[0]
    assert count == 1


def test_save_module(db):
    save_module("mod-1", "Intro to ML", "ml.pdf", db_path=db)
    conn = get_db(db)
    row = conn.execute("SELECT title FROM modules WHERE module_id='mod-1'").fetchone()
    assert row["title"] == "Intro to ML"


def test_save_module_idempotent(db):
    save_module("mod-1", "Intro to ML", "ml.pdf", db_path=db)
    save_module("mod-1", "Intro to ML", "ml.pdf", db_path=db)
    conn = get_db(db)
    count = conn.execute("SELECT COUNT(*) FROM modules WHERE module_id='mod-1'").fetchone()[0]
    assert count == 1


def test_save_attempt_persists(db):
    save_user("u-1", "alice", db_path=db)
    result = make_result("u-1", "mod-1", score=8, total=10)
    save_attempt(result, difficulty="medium", db_path=db)
    conn = get_db(db)
    rows = conn.execute("SELECT * FROM quiz_attempts WHERE user_id='u-1'").fetchall()
    assert len(rows) == 1
    assert rows[0]["score"] == 8
    assert rows[0]["percentage"] == 80.0


def test_get_user_attempts_empty(db):
    attempts = get_user_attempts("nobody", "mod-1", db_path=db)
    assert attempts == []


def test_get_user_attempts_returns_newest_first(db):
    save_user("u-1", "alice", db_path=db)
    r1 = make_result("u-1", "mod-1", score=5, total=10)
    r2 = make_result("u-1", "mod-1", score=8, total=10)
    r2.quiz_id = "quiz-second"
    save_attempt(r1, "easy", db_path=db)
    save_attempt(r2, "hard", db_path=db)
    attempts = get_user_attempts("u-1", "mod-1", db_path=db)
    assert len(attempts) == 2
    assert attempts[0]["score"] == 8


def test_multiple_users_isolated(db):
    save_user("u-1", "alice", db_path=db)
    save_user("u-2", "bob", db_path=db)
    save_attempt(make_result("u-1", "mod-1", 9, 10), "hard", db_path=db)
    save_attempt(make_result("u-2", "mod-1", 4, 10), "easy", db_path=db)
    assert len(get_user_attempts("u-1", "mod-1", db_path=db)) == 1
    assert len(get_user_attempts("u-2", "mod-1", db_path=db)) == 1
