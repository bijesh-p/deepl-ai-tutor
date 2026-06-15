import pytest
import sqlite3
from backend.analytics.db import get_db, get_shared_db
from backend.analytics.persistence import (
    save_user, save_attempt, save_module, load_module,
    list_modules, delete_module, get_user_attempts,
    publish_module, unpublish_module, get_published_modules, load_published_module,
    save_tutor_session, load_tutor_session, delete_tutor_session,
    save_topic_mastery, get_topic_mastery,
)
from backend.analytics.stats import get_module_stats
from backend.quiz.models import QuizResult, AnswerResult


@pytest.fixture
def db():
    conn = get_db(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def shared_db():
    conn = get_shared_db(":memory:")
    yield conn
    conn.close()


def _make_result(quiz_id, module_id, user_id, score, total) -> QuizResult:
    pct = round(score / total * 100, 1)
    return QuizResult(
        quiz_id=quiz_id,
        module_id=module_id,
        user_id=user_id,
        score=score,
        total=total,
        percentage=pct,
        answers=[AnswerResult("q1", [0], [0], True, "correct")],
        completed_at="2026-01-01T00:00:00+00:00",
    )


def _save_test_module(module_id: str, created_by: str, db) -> None:
    save_module(
        module_id=module_id,
        title="Test Module",
        source_filename="test.pdf",
        module_json='{"module_id": "' + module_id + '"}',
        question_bank_json="{}",
        created_by=created_by,
        db=db,
    )


def test_save_and_retrieve_user(db):
    uid = save_user("alice", db=db)
    assert uid
    uid2 = save_user("alice", db=db)
    assert uid == uid2  # idempotent


def test_save_and_load_module(db):
    uid = save_user("admin", db=db)
    _save_test_module("mod-1", uid, db)

    loaded = load_module("mod-1", db=db)
    assert loaded is not None
    assert loaded["title"] == "Test Module"
    assert loaded["source_filename"] == "test.pdf"
    assert loaded["created_by"] == uid


def test_list_and_delete_module(db):
    uid = save_user("admin", db=db)
    _save_test_module("mod-1", uid, db)
    _save_test_module("mod-2", uid, db)

    modules = list_modules(db=db)
    assert len(modules) == 2

    delete_module("mod-1", db=db)
    modules = list_modules(db=db)
    assert len(modules) == 1
    assert modules[0]["module_id"] == "mod-2"


def test_save_attempt_and_get_stats(db):
    uid = save_user("alice", db=db)
    _save_test_module("mod-1", uid, db)

    result = _make_result("quiz-1", "mod-1", uid, score=8, total=10)
    save_attempt(result, "medium", db=db)

    stats = get_module_stats("mod-1", uid, db=db)
    assert stats.total_attempts == 1
    assert stats.user_score == 80.0
    assert stats.avg_score == 80.0


def test_cohort_stats_with_multiple_users(db):
    creator_id = save_user("creator", db=db)
    _save_test_module("mod-1", creator_id, db)

    for name, score in [("alice", 6), ("bob", 8), ("carol", 10)]:
        uid = save_user(name, db=db)
        r = _make_result(f"quiz-{name}", "mod-1", uid, score=score, total=10)
        save_attempt(r, "medium", db=db)

    alice_id = save_user("alice", db=db)
    stats = get_module_stats("mod-1", alice_id, db=db)

    assert stats.total_attempts == 3
    assert stats.min_score == 60.0
    assert stats.max_score == 100.0
    assert stats.avg_score == pytest.approx(80.0, abs=0.2)
    assert stats.user_score == 60.0
    assert stats.user_percentile == 0.0


def test_get_user_attempts(db):
    uid = save_user("alice", db=db)
    _save_test_module("mod-1", uid, db)
    for i in range(3):
        r = _make_result(f"quiz-{i}", "mod-1", uid, score=i + 5, total=10)
        save_attempt(r, "easy", db=db)
    attempts = get_user_attempts(uid, "mod-1", db=db)
    assert len(attempts) == 3


def test_publish_module_copies_to_shared_db(db, shared_db):
    uid = save_user("admin", db=db)
    _save_test_module("mod-1", uid, db)

    publish_module("mod-1", db=db, shared_db=shared_db)

    published = get_published_modules(shared_db)
    assert len(published) == 1
    assert published[0]["module_id"] == "mod-1"
    assert published[0]["created_by"] == uid

    loaded = load_published_module("mod-1", shared_db=shared_db)
    assert loaded is not None
    assert loaded["module_json"] == '{"module_id": "mod-1"}'

    modules = list_modules(db=db)
    assert modules[0]["is_published"] == 1


def test_unpublish_module_removes_from_shared_db(db, shared_db):
    uid = save_user("admin", db=db)
    _save_test_module("mod-1", uid, db)
    publish_module("mod-1", db=db, shared_db=shared_db)

    unpublish_module("mod-1", db=db, shared_db=shared_db)

    assert get_published_modules(shared_db) == []
    modules = list_modules(db=db)
    assert modules[0]["is_published"] == 0


def test_publish_module_not_found_raises(db, shared_db):
    with pytest.raises(ValueError):
        publish_module("missing-mod", db=db, shared_db=shared_db)


def test_save_load_delete_tutor_session(db):
    uid = save_user("alice", db=db)

    assert load_tutor_session(uid, "mod-1", db=db) is None

    state = {"current_concept": "Intro", "attempts": 1, "chat_history": []}
    save_tutor_session(uid, "mod-1", state, "answer", db=db)

    saved = load_tutor_session(uid, "mod-1", db=db)
    assert saved["state"] == state
    assert saved["phase"] == "answer"
    assert saved["updated_at"]

    # Upsert overwrites the existing row
    state["attempts"] = 2
    save_tutor_session(uid, "mod-1", state, "slide", db=db)
    saved = load_tutor_session(uid, "mod-1", db=db)
    assert saved["state"]["attempts"] == 2
    assert saved["phase"] == "slide"

    delete_tutor_session(uid, "mod-1", db=db)
    assert load_tutor_session(uid, "mod-1", db=db) is None


def test_save_and_get_topic_mastery(db):
    uid = save_user("alice", db=db)

    save_topic_mastery(uid, "mod-1", "Intro", mastered=True, difficulty="intermediate", attempts=2, db=db)
    save_topic_mastery(uid, "mod-1", "Loops", mastered=False, difficulty="beginner", attempts=1, db=db)

    rows = {r["topic_id"]: r for r in get_topic_mastery(uid, "mod-1", db=db)}
    assert rows["Intro"]["mastered"] == 1
    assert rows["Intro"]["difficulty"] == "intermediate"
    assert rows["Intro"]["attempts"] == 2
    assert rows["Loops"]["mastered"] == 0

    # Upsert overwrites the existing row
    save_topic_mastery(uid, "mod-1", "Loops", mastered=True, difficulty="beginner", attempts=3, db=db)
    rows = {r["topic_id"]: r for r in get_topic_mastery(uid, "mod-1", db=db)}
    assert rows["Loops"]["mastered"] == 1
    assert rows["Loops"]["attempts"] == 3
    assert len(rows) == 2
