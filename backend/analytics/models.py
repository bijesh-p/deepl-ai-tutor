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


@dataclass
class TopicMasteryRow:
    topic_id: str
    mastered: bool
    difficulty: str
    attempts: int
    last_updated: str | None  # None if the topic hasn't been attempted yet


@dataclass
class MasteryReport:
    module_id: str
    user_id: str
    topics: list[TopicMasteryRow]
    mastered_count: int
    total_count: int


@dataclass
class CohortTopicMastery:
    topic_id: str
    mastered_pct: float   # 0-100, % of users (with any attempt) who mastered it
    avg_attempts: float
    total_users: int


@dataclass
class CohortMastery:
    module_id: str
    topics: list[CohortTopicMastery]
