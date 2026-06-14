from analytics.persistence import save_user, save_attempt
from analytics.stats import get_module_stats
from quiz.models import QuizResult


def _result(quiz_id, module_id, user_id, score, total) -> QuizResult:
    return QuizResult(
        quiz_id=quiz_id,
        module_id=module_id,
        user_id=user_id,
        score=score,
        total=total,
        percentage=round(score / total * 100, 1),
        answers=[],
        completed_at="2026-06-13T00:00:00+00:00",
    )


def _seed_users(conn):
    save_user("u1", "alice", conn)
    save_user("u2", "bob", conn)
    save_user("u3", "carol", conn)


def test_stats_with_multiple_attempts(db_conn):
    _seed_users(db_conn)
    save_attempt(_result("q1", "mod1", "u1", 8, 10), db_conn)   # 80%
    save_attempt(_result("q2", "mod1", "u2", 6, 10), db_conn)   # 60%
    save_attempt(_result("q3", "mod1", "u3", 10, 10), db_conn)  # 100%

    stats = get_module_stats("mod1", "u1", db_conn)

    assert stats.total_attempts == 3
    assert stats.min_score == 60.0
    assert stats.max_score == 100.0
    assert abs(stats.avg_score - 80.0) < 0.1
    assert stats.user_score == 80.0


def test_percentile(db_conn):
    _seed_users(db_conn)
    save_attempt(_result("q1", "mod1", "u1", 4, 10), db_conn)   # 40%
    save_attempt(_result("q2", "mod1", "u2", 6, 10), db_conn)   # 60%
    save_attempt(_result("q3", "mod1", "u3", 8, 10), db_conn)   # 80%

    stats = get_module_stats("mod1", "u2", db_conn)
    # u2 scored 60%; 2 out of 3 scores are <= 60% → ~66.7th percentile
    assert 60 <= stats.user_percentile <= 70


def test_no_attempts_returns_zeros(db_conn):
    stats = get_module_stats("nonexistent", "u1", db_conn)
    assert stats.total_attempts == 0
    assert stats.min_score == 0.0


def test_user_attempt_count(db_conn):
    _seed_users(db_conn)
    save_attempt(_result("q1", "mod1", "u1", 5, 10), db_conn)
    save_attempt(_result("q2", "mod1", "u1", 7, 10), db_conn)

    stats = get_module_stats("mod1", "u1", db_conn)
    assert stats.user_attempts == 2
