from __future__ import annotations

import json
import dataclasses
from dataclasses import dataclass


@dataclass
class QuizQuestion:
    question_id: str
    question_text: str
    question_type: str          # "single_choice" or "multiple_choice"
    options: list[str]
    correct_answers: list[int]
    explanation: str
    difficulty: str             # "easy", "medium", "hard"
    topic_id: str


@dataclass
class QuestionBank:
    module_id: str
    questions: list[QuizQuestion]

    def to_json(self) -> str:
        return json.dumps(dataclasses.asdict(self), indent=2)

    @classmethod
    def from_json(cls, data: str | dict) -> QuestionBank:
        d = json.loads(data) if isinstance(data, str) else data
        return cls(
            module_id=d["module_id"],
            questions=[QuizQuestion(**q) for q in d["questions"]],
        )


@dataclass
class Quiz:
    quiz_id: str
    module_id: str
    difficulty: str
    questions: list[QuizQuestion]
    created_at: str  # ISO 8601


@dataclass
class AnswerResult:
    question_id: str
    selected: list[int]
    correct: list[int]
    is_correct: bool
    explanation: str


@dataclass
class QuizResult:
    quiz_id: str
    module_id: str
    user_id: str
    score: int        # number correct
    total: int
    percentage: float
    answers: list[AnswerResult]
    completed_at: str  # ISO 8601

    def to_json(self) -> str:
        return json.dumps(dataclasses.asdict(self), indent=2)

    @classmethod
    def from_json(cls, data: str | dict) -> QuizResult:
        d = json.loads(data) if isinstance(data, str) else data
        return cls(
            quiz_id=d["quiz_id"],
            module_id=d["module_id"],
            user_id=d["user_id"],
            score=d["score"],
            total=d["total"],
            percentage=d["percentage"],
            answers=[AnswerResult(**a) for a in d["answers"]],
            completed_at=d["completed_at"],
        )
