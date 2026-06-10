from __future__ import annotations

import uuid
from content.llm_client import LLMClient, coerce_tool_array, coerce_tool_item
from content.models import EnrichedTopic, Question

_TOOL_SCHEMA = {
    "name": "return_questions",
    "description": "Return 2 inline comprehension questions for the topic.",
    "input_schema": {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "minItems": 2,
                "maxItems": 2,
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
                            "description": "Zero-based indices of correct option(s).",
                        },
                        "explanation": {"type": "string"},
                    },
                    "required": [
                        "question_text",
                        "question_type",
                        "options",
                        "correct_answers",
                        "explanation",
                    ],
                },
            }
        },
        "required": ["questions"],
    },
}

_SYSTEM = (
    "You are an expert educator writing quick comprehension checks. "
    "Generate exactly 2 questions that test the key concepts of the topic. "
    "Mix single-choice and multiple-choice. Each question must have exactly 4 options."
)


def generate_inline_questions(
    enriched: EnrichedTopic,
    llm: LLMClient,
) -> list[Question]:
    """Generate 2 inline comprehension questions for an enriched topic."""
    prompt = (
        f"Topic: {enriched.topic.title}\n\n"
        f"{enriched.content_md}\n\n"
        "Generate 2 comprehension questions for this topic."
    )

    result = llm.generate(
        prompt=prompt,
        system=_SYSTEM,
        tool_schema=_TOOL_SCHEMA,
    )

    questions: list[Question] = []
    for q in coerce_tool_array(result["questions"]):
        q = coerce_tool_item(q)
        questions.append(
            Question(
                question_id=str(uuid.uuid4()),
                question_text=q["question_text"],
                question_type=q["question_type"],
                options=q["options"],
                correct_answers=q["correct_answers"],
                explanation=q["explanation"],
            )
        )
    return questions
