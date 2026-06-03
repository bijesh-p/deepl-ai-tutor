from __future__ import annotations

import uuid

from content.llm_client import LLMClient
from content.models import LearningModule
from quiz.difficulty import validate_difficulty
from quiz.models import QuestionBank, QuizQuestion

_SYSTEM = (
    "You are an expert at writing exam-quality multiple-choice questions "
    "that test genuine understanding at different cognitive levels. "
    "Always assign each question a difficulty: easy, medium, or hard."
)

_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "question_text": {"type": "string"},
            "question_type": {
                "type": "string",
                "enum": ["single_choice", "multiple_choice"],
            },
            "options": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 4,
                "maxItems": 4,
            },
            "correct_answers": {
                "type": "array",
                "items": {"type": "integer"},
            },
            "explanation": {"type": "string"},
            "difficulty": {
                "type": "string",
                "enum": ["easy", "medium", "hard"],
            },
        },
        "required": [
            "question_text",
            "question_type",
            "options",
            "correct_answers",
            "explanation",
            "difficulty",
        ],
    },
}


def generate_question_bank(module: LearningModule, llm: LLMClient) -> QuestionBank:
    """Generate a pool of 4-6 quiz questions per topic using the LLM.

    Questions are tagged with difficulty during generation.
    The full pool is returned as a QuestionBank for the assembler to draw from.
    """
    all_questions: list[QuizQuestion] = []

    for enriched_topic in module.topics:
        topic = enriched_topic.topic
        prompt = (
            f"Topic: '{topic.title}'\n"
            f"Summary: {topic.summary}\n\n"
            f"Content:\n{enriched_topic.content_md[:1200]}\n\n"
            "Write 4-6 quiz questions covering this topic at a mix of difficulty levels "
            "(at least one easy, one medium, one hard). "
            "Use 'single_choice' when exactly one answer is correct; "
            "'multiple_choice' when multiple options are correct. "
            "Each question must have exactly 4 options. "
            "'correct_answers' is a list of 0-based indices. "
            "Include a clear explanation. "
            "Tag each question with 'difficulty': easy, medium, or hard. "
            "Return a JSON array of question objects."
        )

        raw: list[dict] = llm.generate(prompt, system=_SYSTEM, response_schema=_SCHEMA)

        for item in raw:
            all_questions.append(
                QuizQuestion(
                    question_id=str(uuid.uuid4()),
                    question_text=item["question_text"],
                    question_type=item["question_type"],
                    options=item["options"],
                    correct_answers=item["correct_answers"],
                    explanation=item["explanation"],
                    difficulty=validate_difficulty(item["difficulty"]),
                    topic_id=topic.topic_id,
                )
            )

    return QuestionBank(module_id=module.module_id, questions=all_questions)
