from __future__ import annotations

import uuid
from backend.core.llm_client import BaseLLMClient as LLMClient, coerce_tool_array, coerce_tool_item
from backend.content.models import LearningModule
from backend.quiz.models import BLOOM_LEVELS, QuestionBank, QuizQuestion

_TOOL_SCHEMA = {
    "name": "return_question_bank",
    "description": "Return a bank of quiz questions covering all topics in the module.",
    "input_schema": {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "minItems": 18,
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
                        "bloom_level": {
                            "type": "string",
                            "enum": BLOOM_LEVELS,
                        },
                        "topic_title": {"type": "string"},
                    },
                    "required": [
                        "question_text",
                        "question_type",
                        "options",
                        "correct_answers",
                        "explanation",
                        "bloom_level",
                        "topic_title",
                    ],
                },
            }
        },
        "required": ["questions"],
    },
}

_SYSTEM = (
    "You are an expert graduate-level course instructor writing a comprehensive quiz. "
    "Think step by step about which Bloom's taxonomy cognitive level each question should "
    "target before writing it. Generate 18-24 questions covering all topics in the learning "
    "module, aiming for at least 3 questions per Bloom's taxonomy level below.\n\n"
    "Bloom's taxonomy levels:\n"
    "- remember: retrieve relevant knowledge from long-term memory.\n"
    "- understand: construct meaning from instructional content.\n"
    "- apply: carry out or use a procedure in a given situation.\n"
    "- analyze: break material into parts and determine how the parts relate to one another "
    "and the overall structure.\n"
    "- evaluate: make judgments based on criteria and standards.\n"
    "- create: put elements together to form a coherent whole; reorganize elements into a "
    "new pattern or structure. For create-level questions, ask the student to design, "
    "propose, or construct something new — not just analyze existing material.\n\n"
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
    for q in coerce_tool_array(result["questions"]):
        q = coerce_tool_item(q)
        questions.append(
            QuizQuestion(
                question_id=str(uuid.uuid4()),
                question_text=q["question_text"],
                question_type=q["question_type"],
                options=q["options"],
                correct_answers=q["correct_answers"],
                explanation=q["explanation"],
                bloom_level=q["bloom_level"],
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
