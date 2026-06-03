from __future__ import annotations

import uuid

from content.llm_client import LLMClient
from content.models import EnrichedTopic, Question

_SYSTEM = (
    "You are an expert at writing concise multiple-choice questions that test "
    "genuine understanding, not just memorisation. "
    "Each question must have exactly 4 options with clear correct and incorrect answers."
)

_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "question_text": {"type": "string"},
            "question_type": {"type": "string", "enum": ["single_choice", "multiple_choice"]},
            "options": {"type": "array", "items": {"type": "string"}, "minItems": 4, "maxItems": 4},
            "correct_answers": {"type": "array", "items": {"type": "integer"}},
            "explanation": {"type": "string"},
        },
        "required": ["question_text", "question_type", "options", "correct_answers", "explanation"],
    },
}


def generate_inline_questions(topic: EnrichedTopic, llm: LLMClient) -> list[Question]:
    """Generate 2-3 inline reinforcement questions for a topic.

    Questions are embedded in the learning module viewer and give immediate
    feedback — they are distinct from the comprehensive end-of-module quiz.
    """
    prompt = (
        f"Topic: '{topic.topic.title}'\n\n"
        f"Content summary: {topic.topic.summary}\n\n"
        f"Key takeaways:\n" + "\n".join(f"- {t}" for t in topic.key_takeaways) + "\n\n"
        "Write exactly 2-3 short comprehension questions for this topic. "
        "Use 'single_choice' when only one answer is correct; "
        "'multiple_choice' when multiple options are correct. "
        "Each question must have exactly 4 options. "
        "correct_answers is a list of 0-based indices of the correct option(s). "
        "Include a clear explanation shown after the student answers. "
        "Return a JSON array of question objects."
    )

    raw: list[dict] = llm.generate(prompt, system=_SYSTEM, response_schema=_SCHEMA)

    questions: list[Question] = []
    for item in raw[:3]:  # cap at 3
        questions.append(
            Question(
                question_id=str(uuid.uuid4()),
                question_text=item["question_text"],
                question_type=item["question_type"],
                options=item["options"],
                correct_answers=item["correct_answers"],
                explanation=item["explanation"],
            )
        )
    return questions
