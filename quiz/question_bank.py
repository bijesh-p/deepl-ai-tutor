from __future__ import annotations

import uuid
from content.llm_client import LLMClient
from content.models import LearningModule
from quiz.models import QuestionBank, QuizQuestion

_TOOL_SCHEMA = {
    "name": "return_question_bank",
    "description": "Return a bank of quiz questions covering all topics in the module.",
    "input_schema": {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "minItems": 5,
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
                        "topic_title": {"type": "string"},
                    },
                    "required": [
                        "question_text",
                        "question_type",
                        "options",
                        "correct_answers",
                        "explanation",
                        "difficulty",
                        "topic_title",
                    ],
                },
            }
        },
        "required": ["questions"],
    },
}

_SYSTEM = (
    "You are an expert educator writing a comprehensive quiz. "
    "Generate 10-20 questions covering all topics in the learning module. "
    "Include a mix of easy, medium, and hard questions. "
    "Cover recall, understanding, and application cognitive levels. "
    "Each question must have exactly 4 options."
)


def generate_question_bank(module: LearningModule, llm: LLMClient) -> QuestionBank:
    """Generate a question bank from a LearningModule."""
    module_summary = _format_module(module)

    result = llm.generate(
        prompt=f"Generate a question bank for the following learning module:\n\n{module_summary}",
        system=_SYSTEM,
        tool_schema=_TOOL_SCHEMA,
    )

    if "questions" not in result:
        raise RuntimeError(
            f"Question bank LLM response missing 'questions' key. "
            f"Got keys: {list(result.keys())}. Response may have been truncated."
        )

    topic_id_map = {et.topic.title: et.topic.topic_id for et in module.topics}

    questions: list[QuizQuestion] = []
    for q in result["questions"]:
        questions.append(
            QuizQuestion(
                question_id=str(uuid.uuid4()),
                question_text=q["question_text"],
                question_type=q["question_type"],
                options=q["options"],
                correct_answers=q["correct_answers"],
                explanation=q["explanation"],
                difficulty=q["difficulty"],
                topic_id=topic_id_map.get(q["topic_title"], ""),
            )
        )

    return QuestionBank(module_id=module.module_id, questions=questions)


def _format_module(module: LearningModule) -> str:
    parts = [f"Module: {module.title}\n"]
    for et in module.topics:
        parts.append(
            f"Topic: {et.topic.title}\nSummary: {et.topic.summary}\n{et.content_md}"
        )
    return "\n\n".join(parts)
