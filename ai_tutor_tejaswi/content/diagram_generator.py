from __future__ import annotations
import uuid

from content._utils import parse_json_response
from content.llm_client import LLMClient
from content.models import Diagram, EnrichedTopic


def generate_diagrams(topic: EnrichedTopic, llm: LLMClient) -> list[Diagram]:
    system = "You are an expert at creating educational Mermaid diagrams."
    prompt = f"""For the learning topic below, decide if a diagram would aid understanding.
If yes, generate valid Mermaid code. If no diagram is needed, return an empty array.

Topic: {topic.topic.title}
Content excerpt:
{topic.content_html[:800]}

Return JSON:
{{
  "diagrams": [
    {{
      "caption": "Short description of what the diagram shows",
      "mermaid_code": "graph TD\\n  A --> B"
    }}
  ]
}}

Rules:
- Only include a diagram when it genuinely clarifies the content (process, hierarchy, timeline, comparison)
- Use flowchart/graph for processes, classDiagram for hierarchies, sequenceDiagram for interactions
- Mermaid code must be syntactically valid
- Return at most 2 diagrams; return empty array if none fit"""

    result = llm.generate(prompt, system, response_schema={})
    data = parse_json_response(result)

    if isinstance(data, dict):
        items = data.get("diagrams", [])
    else:
        items = data if isinstance(data, list) else []

    return [
        Diagram(
            diagram_id=str(uuid.uuid4()),
            diagram_type="mermaid",
            content=item.get("mermaid_code", ""),
            caption=item.get("caption", ""),
        )
        for item in items
        if item.get("mermaid_code", "").strip()
    ]
