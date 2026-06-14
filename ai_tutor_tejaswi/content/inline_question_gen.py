from __future__ import annotations
import uuid

from content._utils import parse_json_response
from content.llm_client import LLMClient
from content.models import EnrichedTopic, Question


def generate_inline_questions(topic: EnrichedTopic, llm: LLMClient) -> list[Question]:
    system = "You are an expert at writing educational comprehension questions."
    prompt = f"""Write 2-3 quick comprehension questions for the sub-topic below.
These are lightweight 'check your understanding' questions, not exam questions.

Topic: {topic.topic.title}
Key takeaways:
{chr(10).join(f'- {t}' for t in topic.key_takeaways)}

Content:
{topic.content_html[:600]}

Return JSON:
{{
  "questions": [
    {{
      "question_text": "Question?",
      "question_type": "single_choice",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_answers": [0],
      "explanation": "Why A is correct"
    }}
  ]
}}

Rules:
- question_type: "single_choice" (one answer) or "multiple_choice" (multiple correct)
- Always provide exactly 4 options
- correct_answers is a list of 0-based indices
- Keep questions focused on the topic's key concepts"""

    result = llm.generate(prompt, system, response_schema={})
    data = parse_json_response(result)

    if isinstance(data, dict):
        items = data.get("questions", [])
    else:
        items = data if isinstance(data, list) else []

    questions: list[Question] = []
    for item in items:
        options = item.get("options", [])
        if len(options) != 4:
            continue
        questions.append(
            Question(
                question_id=str(uuid.uuid4()),
                question_text=item["question_text"],
                question_type=item.get("question_type", "single_choice"),
                options=options,
                correct_answers=item.get("correct_answers", [0]),
                explanation=item.get("explanation", ""),
            )
        )

    return questions[:3]
