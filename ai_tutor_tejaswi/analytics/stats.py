from __future__ import annotations
import sqlite3

from analytics.db import get_db
from analytics.models import ModuleStats


def get_module_stats(
    module_id: str,
    user_id: str,
    conn: sqlite3.Connection | None = None,
) -> ModuleStats:
    owned = conn is None
    if owned:
        conn = get_db()

    all_rows = conn.execute(
        "SELECT percentage FROM quiz_attempts WHERE module_id = ?",
        (module_id,),
    ).fetchall()

    percentages = [r["percentage"] for r in all_rows]

    user_row = conn.execute(
        """SELECT percentage FROM quiz_attempts
           WHERE module_id = ? AND user_id = ?
           ORDER BY completed_at DESC LIMIT 1""",
        (module_id, user_id),
    ).fetchone()

    user_count_row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM quiz_attempts WHERE module_id = ? AND user_id = ?",
        (module_id, user_id),
    ).fetchone()

    if owned:
        conn.close()

    user_score = user_row["percentage"] if user_row else 0.0
    user_attempts = user_count_row["cnt"] if user_count_row else 0

    if not percentages:
        return ModuleStats(
            module_id=module_id,
            total_attempts=0,
            min_score=0.0,
            max_score=0.0,
            avg_score=0.0,
            user_score=user_score,
            user_percentile=0.0,
            user_attempts=user_attempts,
        )

    percentile = (
        sum(1 for p in percentages if p <= user_score) / len(percentages) * 100
    )

    return ModuleStats(
        module_id=module_id,
        total_attempts=len(percentages),
        min_score=round(min(percentages), 1),
        max_score=round(max(percentages), 1),
        avg_score=round(sum(percentages) / len(percentages), 1),
        user_score=user_score,
        user_percentile=round(percentile, 1),
        user_attempts=user_attempts,
    )
