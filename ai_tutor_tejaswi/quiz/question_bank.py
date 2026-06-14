from __future__ import annotations
import uuid

from content._utils import parse_json_response
from content.llm_client import LLMClient
from content.models import LearningModule
from quiz.models import QuestionBank, QuizQuestion


_PER_TOPIC = 5  # questions generated per topic


def generate_question_bank(module: LearningModule, llm: LLMClient) -> QuestionBank:
    all_questions: list[QuizQuestion] = []

    for et in module.topics:
        questions = _generate_for_topic(et.topic.topic_id, et.topic.title, et.content_html, llm)
        all_questions.extend(questions)

    return QuestionBank(module_id=module.module_id, questions=all_questions)


def _generate_for_topic(
    topic_id: str, topic_title: str, content: str, llm: LLMClient
) -> list[QuizQuestion]:
    system = "You are an expert at writing educational assessment questions at multiple cognitive levels."
    prompt = f"""Write {_PER_TOPIC} exam-quality questions for the topic below.
Cover recall, understanding, and application (mix of difficulty levels).

Topic: {topic_title}
Content:
{content[:800]}

Return JSON:
{{
  "questions": [
    {{
      "question_text": "Question?",
      "question_type": "single_choice",
      "options": ["A", "B", "C", "D"],
      "correct_answers": [0],
      "explanation": "Why A is correct",
      "difficulty": "easy"
    }}
  ]
}}

Rules:
- question_type: "single_choice" or "multiple_choice"
- Always exactly 4 options
- difficulty: "easy", "medium", or "hard"
- Include a mix across all three difficulties"""

    result = llm.generate(prompt, system, response_schema={})
    data = parse_json_response(result)

    if isinstance(data, dict):
        items = data.get("questions", [])
    else:
        items = data if isinstance(data, list) else []

    questions: list[QuizQuestion] = []
    for item in items:
        options = item.get("options", [])
        if len(options) != 4:
            continue
        difficulty = item.get("difficulty", "medium")
        if difficulty not in ("easy", "medium", "hard"):
            difficulty = "medium"
        questions.append(
            QuizQuestion(
                question_id=str(uuid.uuid4()),
                question_text=item["question_text"],
                question_type=item.get("question_type", "single_choice"),
                options=options,
                correct_answers=item.get("correct_answers", [0]),
                explanation=item.get("explanation", ""),
                difficulty=difficulty,
                topic_id=topic_id,
            )
        )

    return questions
