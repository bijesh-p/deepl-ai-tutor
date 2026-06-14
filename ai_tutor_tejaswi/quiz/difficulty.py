from __future__ import annotations

from content._utils import parse_json_response
from content.llm_client import LLMClient
from quiz.models import QuestionBank, QuizQuestion

_VALID = {"easy", "medium", "hard"}
_BATCH = 10


def classify_difficulty(bank: QuestionBank, llm: LLMClient) -> QuestionBank:
    """Classifies any questions that are missing a valid difficulty tag."""
    unclassified = [q for q in bank.questions if q.difficulty not in _VALID]
    if not unclassified:
        return bank

    for i in range(0, len(unclassified), _BATCH):
        _classify_batch(unclassified[i : i + _BATCH], llm)

    return bank


def _classify_batch(questions: list[QuizQuestion], llm: LLMClient) -> None:
    listings = "\n".join(
        f'{i}. [{q.question_id}] {q.question_text}' for i, q in enumerate(questions)
    )
    prompt = f"""Classify each question as "easy", "medium", or "hard" based on cognitive demand.

{listings}

Return JSON:
{{
  "classifications": [
    {{"question_id": "<id>", "difficulty": "easy|medium|hard"}}
  ]
}}"""

    result = llm.generate(prompt, response_schema={})
    data = parse_json_response(result)

    if isinstance(data, dict):
        items = data.get("classifications", [])
    else:
        items = data if isinstance(data, list) else []

    id_map = {q.question_id: q for q in questions}
    for item in items:
        qid = item.get("question_id")
        diff = item.get("difficulty", "medium")
        if qid in id_map and diff in _VALID:
            id_map[qid].difficulty = diff
