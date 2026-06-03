from __future__ import annotations

import json
import dataclasses
from dataclasses import dataclass


@dataclass
class ModuleStats:
    module_id: str
    total_attempts: int
    min_score: float    # minimum percentage across all attempts
    max_score: float    # maximum percentage
    avg_score: float    # average percentage
    user_score: float   # this user's latest percentage
    user_percentile: float  # percentile rank 0-100
    user_attempts: int  # how many times this user attempted

    def to_json(self) -> str:
        return json.dumps(dataclasses.asdict(self), indent=2)

    @classmethod
    def from_json(cls, data: str | dict) -> ModuleStats:
        d = json.loads(data) if isinstance(data, str) else data
        return cls(**d)
