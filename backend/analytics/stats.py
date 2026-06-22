from __future__ import annotations

import json
import sqlite3
from backend.analytics.db import get_db
from backend.analytics.models import (
    CohortMastery,
    CohortTopicMastery,
    MasteryReport,
    ModuleStats,
    TopicMasteryRow,
)


def get_module_stats(module_id: str, user_id: str, db: sqlite3.Connection | None = None) -> ModuleStats:
    """Compute aggregate quiz statistics for a module."""
    conn = db or get_db()

    all_rows = conn.execute(
        "SELECT percentage FROM quiz_attempts WHERE module_id = ?",
        (module_id,),
    ).fetchall()

    percentages = [r["percentage"] for r in all_rows]
    total_attempts = len(percentages)

    if not percentages:
        return ModuleStats(
            module_id=module_id,
            total_attempts=0,
            min_score=0.0,
            max_score=0.0,
            avg_score=0.0,
            user_score=0.0,
            user_percentile=0.0,
            user_attempts=0,
        )

    user_rows = conn.execute(
        """
        SELECT percentage FROM quiz_attempts
        WHERE module_id = ? AND user_id = ?
        ORDER BY completed_at DESC LIMIT 1
        """,
        (module_id, user_id),
    ).fetchone()
    user_score = user_rows["percentage"] if user_rows else 0.0

    user_attempt_count = conn.execute(
        "SELECT COUNT(*) as c FROM quiz_attempts WHERE module_id = ? AND user_id = ?",
        (module_id, user_id),
    ).fetchone()["c"]

    below = sum(1 for p in percentages if p < user_score)
    user_percentile = round(below / total_attempts * 100, 1)

    return ModuleStats(
        module_id=module_id,
        total_attempts=total_attempts,
        min_score=round(min(percentages), 1),
        max_score=round(max(percentages), 1),
        avg_score=round(sum(percentages) / total_attempts, 1),
        user_score=round(user_score, 1),
        user_percentile=user_percentile,
        user_attempts=user_attempt_count,
    )


def get_mastery_report(
    module_id: str,
    user_id: str,
    topic_order: list[str],
    db: sqlite3.Connection | None = None,
) -> MasteryReport:
    """Build a per-topic mastery report for a user, ordered as in `topic_order`."""
    conn = db or get_db()

    rows = conn.execute(
        """
        SELECT topic_id, mastered, difficulty, attempts, last_updated
        FROM topic_mastery WHERE user_id = ? AND module_id = ?
        """,
        (user_id, module_id),
    ).fetchall()
    by_topic = {r["topic_id"]: r for r in rows}

    topics = []
    for topic_id in topic_order:
        row = by_topic.get(topic_id)
        if row:
            topics.append(
                TopicMasteryRow(
                    topic_id=topic_id,
                    mastered=bool(row["mastered"]),
                    difficulty=row["difficulty"],
                    attempts=row["attempts"],
                    last_updated=row["last_updated"],
                )
            )
        else:
            topics.append(
                TopicMasteryRow(
                    topic_id=topic_id,
                    mastered=False,
                    difficulty="—",
                    attempts=0,
                    last_updated=None,
                )
            )

    mastered_count = sum(1 for t in topics if t.mastered)

    return MasteryReport(
        module_id=module_id,
        user_id=user_id,
        topics=topics,
        mastered_count=mastered_count,
        total_count=len(topics),
    )


def get_cohort_mastery(
    module_id: str,
    topic_order: list[str],
    db: sqlite3.Connection | None = None,
) -> CohortMastery:
    """Aggregate per-topic mastery across all users for a module."""
    conn = db or get_db()

    rows = conn.execute(
        """
        SELECT topic_id, AVG(mastered) * 100 AS mastered_pct, AVG(attempts) AS avg_attempts,
               COUNT(DISTINCT user_id) AS total_users
        FROM topic_mastery WHERE module_id = ?
        GROUP BY topic_id
        """,
        (module_id,),
    ).fetchall()
    by_topic = {r["topic_id"]: r for r in rows}

    topics = []
    for topic_id in topic_order:
        row = by_topic.get(topic_id)
        if row:
            topics.append(
                CohortTopicMastery(
                    topic_id=topic_id,
                    mastered_pct=round(row["mastered_pct"], 1),
                    avg_attempts=round(row["avg_attempts"], 1),
                    total_users=row["total_users"],
                )
            )
        else:
            topics.append(
                CohortTopicMastery(
                    topic_id=topic_id,
                    mastered_pct=0.0,
                    avg_attempts=0.0,
                    total_users=0,
                )
            )

    return CohortMastery(module_id=module_id, topics=topics)


def get_eval_results(
    user_id: str,
    limit: int = 20,
    db: sqlite3.Connection | None = None,
) -> list[dict]:
    """Return recent DeepEval session results for a user, most recent first.

    Each entry:
      {
        "module_id", "title", "evaluated_at",
        "raw_scores": [{"metric", "score", "threshold", "passed", "reason"}, ...],
        "aggregated": {"MetricName": {"mean": float, "pass_rate": float, "count": int}, ...},
      }

    aggregated is computed at read time — mean score and pass-rate per metric
    across all test cases in the session.
    """
    conn = db or get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eval_results (
            result_id    TEXT PRIMARY KEY,
            user_id      TEXT NOT NULL,
            module_id    TEXT NOT NULL,
            scores_json  TEXT NOT NULL,
            evaluated_at TEXT NOT NULL
        )
    """)
    rows = conn.execute(
        """
        SELECT e.module_id, COALESCE(m.title, '') AS title,
               e.scores_json, e.evaluated_at
        FROM eval_results e
        LEFT JOIN modules m ON e.module_id = m.module_id
        WHERE e.user_id = ?
        ORDER BY e.evaluated_at DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()

    results = []
    for r in rows:
        raw_scores: list[dict] = json.loads(r["scores_json"])
        # Aggregate per metric: collect scores and pass flags
        agg: dict[str, dict] = {}
        for s in raw_scores:
            metric = s.get("metric", "unknown")
            score = s.get("score")
            passed = s.get("passed")
            if metric not in agg:
                agg[metric] = {"scores": [], "passed": []}
            if score is not None:
                agg[metric]["scores"].append(score)
            if passed is not None:
                agg[metric]["passed"].append(bool(passed))

        aggregated: dict[str, dict] = {}
        for metric, data in agg.items():
            scores_list = data["scores"]
            passed_list = data["passed"]
            aggregated[metric] = {
                "mean": round(sum(scores_list) / len(scores_list), 3) if scores_list else None,
                "pass_rate": round(sum(passed_list) / len(passed_list), 3) if passed_list else None,
                "count": len(scores_list),
            }

        results.append({
            "module_id": r["module_id"],
            "title": r["title"],
            "evaluated_at": r["evaluated_at"],
            "raw_scores": raw_scores,
            "aggregated": aggregated,
        })
    return results
