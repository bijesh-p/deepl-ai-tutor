from __future__ import annotations

import pytest
from datetime import datetime, timezone

from backend.analytics.db import get_db
from backend.analytics.models import ModuleStats
from backend.analytics.persistence import save_attempt, save_user
from backend.analytics.stats import get_module_stats
from backend.quiz.models import AnswerResult, QuizResult


def make_result(user_id: str, module_id: str, score: int, total: int) -> QuizResult:
    pct = round((score / total) * 100, 2)
    return QuizResult(
        quiz_id=f"quiz-{user_id}-{score}",
        module_id=module_id,
        user_id=user_id,
        score=score,
        total=total,
        percentage=pct,
        answers=[AnswerResult("q-1", [0], [0], True, "explanation")],
        completed_at=datetime.now(timezone.utc).isoformat(),
    )


@pytest.fixture
def db():
    conn = get_db(":memory:")
    yield conn
    conn.close()


def seed(db, scores_by_user: dict[str, int], module_id: str = "mod-1"):
    creator_id = save_user("creator", db=db)
    from backend.analytics.persistence import save_module
    save_module(
        module_id=module_id,
        title="Test Module",
        source_filename="test.pdf",
        module_json='{}',
        question_bank_json='{}',
        created_by=creator_id,
        db=db,
    )
    for username, score in scores_by_user.items():
        uid = save_user(username, db=db)
        save_attempt(make_result(uid, module_id, score, 10), "medium", db=db)


def test_returns_module_stats_type(db):
    seed(db, {"u-1": 7})
    uid = save_user("u-1", db=db)
    stats = get_module_stats("mod-1", uid, db=db)
    assert isinstance(stats, ModuleStats)


def test_no_attempts_returns_zeros(db):
    stats = get_module_stats("mod-empty", "u-1", db=db)
    assert stats.total_attempts == 0
    assert stats.user_score == 0.0
    assert stats.user_percentile == 0.0


def test_single_attempt_percentile(db):
    seed(db, {"u-1": 8})
    uid = save_user("u-1", db=db)
    stats = get_module_stats("mod-1", uid, db=db)
    assert stats.total_attempts == 1
    assert stats.user_percentile == 0.0  # no scores below → 0th percentile


def test_min_max_avg_correct(db):
    seed(db, {"u-1": 4, "u-2": 6, "u-3": 8, "u-4": 10})
    uid = save_user("u-1", db=db)
    stats = get_module_stats("mod-1", uid, db=db)
    assert stats.total_attempts == 4
    assert stats.min_score == 40.0
    assert stats.max_score == 100.0
    assert stats.avg_score == 70.0


def test_user_score_is_latest(db):
    uid = save_user("u-1", db=db)
    from backend.analytics.persistence import save_module
    save_module(
        module_id="mod-1",
        title="Test",
        source_filename="t.pdf",
        module_json="{}",
        question_bank_json="{}",
        created_by=uid,
        db=db,
    )
    save_attempt(make_result(uid, "mod-1", 3, 10), "easy", db=db)
    r2 = make_result(uid, "mod-1", 9, 10)
    r2.quiz_id = "quiz-second"
    save_attempt(r2, "hard", db=db)
    stats = get_module_stats("mod-1", uid, db=db)
    assert stats.user_score == 90.0


def test_percentile_calculation(db):
    # Scores: 40, 60, 70, 80, 100 → user=70, 2 strictly below → 40th percentile
    seed(db, {"u-1": 4, "u-2": 6, "u-3": 7, "u-4": 8, "u-5": 10})
    uid = save_user("u-3", db=db)
    stats = get_module_stats("mod-1", uid, db=db)
    assert stats.user_percentile == 40.0


def test_user_attempts_count(db):
    uid = save_user("u-1", db=db)
    from backend.analytics.persistence import save_module
    save_module(
        module_id="mod-1",
        title="Test",
        source_filename="t.pdf",
        module_json="{}",
        question_bank_json="{}",
        created_by=uid,
        db=db,
    )
    for i in range(3):
        r = make_result(uid, "mod-1", i + 5, 10)
        r.quiz_id = f"quiz-{i}"
        save_attempt(r, "medium", db=db)
    stats = get_module_stats("mod-1", uid, db=db)
    assert stats.user_attempts == 3


def test_module_id_in_stats(db):
    seed(db, {"u-1": 5})
    uid = save_user("u-1", db=db)
    stats = get_module_stats("mod-1", uid, db=db)
    assert stats.module_id == "mod-1"
