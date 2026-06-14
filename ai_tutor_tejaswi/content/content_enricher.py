from __future__ import annotations

from content._utils import parse_json_response
from content.llm_client import LLMClient
from content.models import EnrichedTopic, Topic


def enrich(topic: Topic, llm: LLMClient, raw_content: str = "") -> EnrichedTopic:
    system = (
        "You are an expert educator. Rewrite educational content to be clear, "
        "engaging, and learner-friendly while preserving all original facts."
    )
    prompt = f"""Enrich the following learning sub-topic.

Topic: {topic.title}
Summary: {topic.summary}
Raw content:
{raw_content or "(generate based on the topic title and summary)"}

Return JSON:
{{
  "content_html": "Enriched Markdown — use ## headers, bullets, **bold** for key terms, analogies, examples",
  "key_takeaways": ["takeaway 1", "takeaway 2", "takeaway 3"]
}}

Rules:
- Preserve all facts; add clarity and examples, not new claims
- Add a '## Key Definitions' section when important terms appear
- Keep key_takeaways to 3-5 items, one sentence each"""

    result = llm.generate(prompt, system, response_schema={})
    data = parse_json_response(result)

    return EnrichedTopic(
        topic=topic,
        content_html=data.get("content_html", f"## {topic.title}\n\n{raw_content}"),
        key_takeaways=data.get("key_takeaways", []),
    )
