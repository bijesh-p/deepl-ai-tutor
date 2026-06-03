from __future__ import annotations

from analytics.db import get_db
from analytics.models import ModuleStats


def get_module_stats(
    module_id: str,
    user_id: str,
    db_path: str | None = None,
) -> ModuleStats:
    """Compute cohort statistics for a module and this user's standing.

    Percentile = (number of attempts with percentage <= user's latest score)
                 / total attempts × 100.
    Edge case: if the user has no prior attempts, returns a ModuleStats with
    zero totals and 0.0 percentile. If the user is the only attempt,
    percentile = 100.0.
    """
    conn = get_db(db_path)

    # All attempts for the module
    all_rows = conn.execute(
        "SELECT percentage FROM quiz_attempts WHERE module_id = ?",
        (module_id,),
    ).fetchall()

    # User's latest attempt
    user_row = conn.execute(
        """SELECT percentage FROM quiz_attempts
           WHERE module_id = ? AND user_id = ?
           ORDER BY completed_at DESC LIMIT 1""",
        (module_id, user_id),
    ).fetchone()

    # User attempt count
    user_attempts = conn.execute(
        "SELECT COUNT(*) FROM quiz_attempts WHERE module_id = ? AND user_id = ?",
        (module_id, user_id),
    ).fetchone()[0]

    conn.close()

    total = len(all_rows)
    if total == 0 or user_row is None:
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

    scores = [r["percentage"] for r in all_rows]
    user_score = user_row["percentage"]

    at_or_below = sum(1 for s in scores if s <= user_score)
    percentile = round((at_or_below / total) * 100, 2)

    return ModuleStats(
        module_id=module_id,
        total_attempts=total,
        min_score=round(min(scores), 2),
        max_score=round(max(scores), 2),
        avg_score=round(sum(scores) / total, 2),
        user_score=user_score,
        user_percentile=percentile,
        user_attempts=user_attempts,
    )
