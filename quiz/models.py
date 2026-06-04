from __future__ import annotations

from dataclasses import dataclass, field


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


@dataclass
class Quiz:
    quiz_id: str
    module_id: str
    difficulty: str
    questions: list[QuizQuestion]
    created_at: str             # ISO 8601


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
    score: int
    total: int
    percentage: float
    answers: list[AnswerResult]
    completed_at: str           # ISO 8601
