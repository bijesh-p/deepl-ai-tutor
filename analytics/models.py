from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModuleStats:
    module_id: str
    total_attempts: int
    min_score: float        # minimum percentage across all attempts
    max_score: float
    avg_score: float
    user_score: float       # this user's latest percentage
    user_percentile: float  # 0-100
    user_attempts: int
