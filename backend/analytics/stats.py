from __future__ import annotations

import sqlite3
from backend.analytics.db import get_db
from backend.analytics.models import ModuleStats


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
