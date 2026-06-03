from __future__ import annotations

import pytest
from datetime import datetime, timezone

from analytics.models import ModuleStats
from analytics.persistence import save_attempt, save_user
from analytics.stats import get_module_stats
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
        answers=[AnswerResult("q-1", [0], [0], True, "explanation")],
        completed_at=datetime.now(timezone.utc).isoformat(),
    )


@pytest.fixture
def db(tmp_path) -> str:
    return str(tmp_path / "test.db")


def seed(db: str, scores_by_user: dict[str, int], module_id: str = "mod-1"):
    for user_id, score in scores_by_user.items():
        save_user(user_id, user_id, db_path=db)
        save_attempt(make_result(user_id, module_id, score, 10), "medium", db_path=db)


def test_returns_module_stats_type(db):
    seed(db, {"u-1": 7})
    stats = get_module_stats("mod-1", "u-1", db_path=db)
    assert isinstance(stats, ModuleStats)


def test_no_attempts_returns_zeros(db):
    stats = get_module_stats("mod-empty", "u-1", db_path=db)
    assert stats.total_attempts == 0
    assert stats.user_score == 0.0
    assert stats.user_percentile == 0.0


def test_single_attempt_percentile_100(db):
    seed(db, {"u-1": 8})
    stats = get_module_stats("mod-1", "u-1", db_path=db)
    assert stats.total_attempts == 1
    assert stats.user_percentile == 100.0


def test_min_max_avg_correct(db):
    seed(db, {"u-1": 4, "u-2": 6, "u-3": 8, "u-4": 10})
    stats = get_module_stats("mod-1", "u-1", db_path=db)
    assert stats.total_attempts == 4
    assert stats.min_score == 40.0
    assert stats.max_score == 100.0
    assert stats.avg_score == 70.0  # (40+60+80+100)/4


def test_user_score_is_latest(db):
    save_user("u-1", "alice", db_path=db)
    save_attempt(make_result("u-1", "mod-1", 3, 10), "easy", db_path=db)
    r2 = make_result("u-1", "mod-1", 9, 10)
    r2.quiz_id = "quiz-second"
    save_attempt(r2, "hard", db_path=db)
    stats = get_module_stats("mod-1", "u-1", db_path=db)
    assert stats.user_score == 90.0


def test_percentile_calculation(db):
    # Scores: 40, 60, 70, 80, 100 → user=70, 3 at-or-below → 60th percentile
    seed(db, {"u-1": 4, "u-2": 6, "u-3": 7, "u-4": 8, "u-5": 10})
    stats = get_module_stats("mod-1", "u-3", db_path=db)
    assert stats.user_percentile == 60.0


def test_user_attempts_count(db):
    save_user("u-1", "alice", db_path=db)
    for i in range(3):
        r = make_result("u-1", "mod-1", i + 5, 10)
        r.quiz_id = f"quiz-{i}"
        save_attempt(r, "medium", db_path=db)
    stats = get_module_stats("mod-1", "u-1", db_path=db)
    assert stats.user_attempts == 3


def test_module_id_in_stats(db):
    seed(db, {"u-1": 5})
    stats = get_module_stats("mod-1", "u-1", db_path=db)
    assert stats.module_id == "mod-1"
