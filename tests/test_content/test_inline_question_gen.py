from backend.content.inline_question_gen import generate_inline_questions
from backend.content.models import Diagram, EnrichedTopic, Topic


class _MockLLM:
    def __init__(self, response):
        self.response = response
        self.calls: list[dict] = []

    def generate(self, prompt, system=None, tool_schema=None, cached_blocks=None):
        self.calls.append({"prompt": prompt, "system": system, "tool_schema": tool_schema})
        return self.response


def _make_enriched_topic() -> EnrichedTopic:
    topic = Topic(
        topic_id="t1",
        title="Photosynthesis",
        summary="Plants convert light to energy.",
        source_section_ids=["s1"],
        order=0,
    )
    return EnrichedTopic(
        topic=topic,
        content_md="# Photosynthesis\n\nPlants use light to make energy.",
        key_takeaways=["Light drives the reaction"],
        diagrams=[],
        inline_questions=[],
    )


def test_generate_inline_questions_populates_bloom_level():
    response = {
        "questions": [
            {
                "question_text": "What pigment absorbs light?",
                "question_type": "single_choice",
                "options": ["Chlorophyll", "Melanin", "Haemoglobin", "Keratin"],
                "correct_answers": [0],
                "explanation": "Chlorophyll absorbs light for photosynthesis.",
                "bloom_level": "remember",
            },
            {
                "question_text": "How would you apply photosynthesis to estimate plant growth?",
                "question_type": "single_choice",
                "options": ["More light, more growth", "Light is irrelevant", "Only soil matters", "Only water matters"],
                "correct_answers": [0],
                "explanation": "More light generally drives more photosynthesis and growth.",
                "bloom_level": "apply",
            },
        ]
    }
    enriched = _make_enriched_topic()
    questions = generate_inline_questions(enriched, _MockLLM(response))

    assert len(questions) == 2
    assert questions[0].bloom_level == "remember"
    assert questions[1].bloom_level == "apply"


def test_generate_inline_questions_schema_requires_bloom_level():
    response = {
        "questions": [
            {
                "question_text": "Q1?",
                "question_type": "single_choice",
                "options": ["A", "B", "C", "D"],
                "correct_answers": [0],
                "explanation": "Because A.",
                "bloom_level": "understand",
            },
            {
                "question_text": "Q2?",
                "question_type": "multiple_choice",
                "options": ["A", "B", "C", "D"],
                "correct_answers": [0, 1],
                "explanation": "Because A and B.",
                "bloom_level": "apply",
            },
        ]
    }
    enriched = _make_enriched_topic()
    llm = _MockLLM(response)
    generate_inline_questions(enriched, llm)

    schema = llm.calls[0]["tool_schema"]
    item_schema = schema["input_schema"]["properties"]["questions"]["items"]
    assert "bloom_level" in item_schema["required"]
    assert set(item_schema["properties"]["bloom_level"]["enum"]) == {"remember", "understand", "apply"}
