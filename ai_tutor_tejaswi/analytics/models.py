from __future__ import annotations
from dataclasses import dataclass


@dataclass
class ModuleStats:
    module_id: str
    total_attempts: int
    min_score: float
    max_score: float
    avg_score: float
    user_score: float
    user_percentile: float
    user_attempts: int
