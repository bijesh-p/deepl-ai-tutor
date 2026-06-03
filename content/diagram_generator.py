from __future__ import annotations

import uuid

from content.llm_client import LLMClient
from content.models import Diagram, EnrichedTopic
from ingestion.models import ExtractedImage

_SYSTEM = (
    "You are an expert at creating clear educational diagrams using Mermaid syntax. "
    "Only suggest a diagram when it genuinely adds understanding beyond the text. "
    "Always produce valid Mermaid syntax with a descriptive title in frontmatter."
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "needs_diagram": {"type": "boolean"},
        "mermaid_code": {"type": "string"},
        "caption": {"type": "string"},
    },
    "required": ["needs_diagram"],
}


def generate_diagrams(
    topic: EnrichedTopic,
    llm: LLMClient,
    extracted_images: list[ExtractedImage] | None = None,
) -> list[Diagram]:
    """Generate Mermaid diagrams for a topic and include any extracted images.

    The LLM decides whether a diagram adds value. If yes, it returns Mermaid
    code which is stored as a Diagram with diagram_type='mermaid'.
    Extracted images from the original document are appended as
    diagram_type='extracted_image'.
    """
    diagrams: list[Diagram] = []

    prompt = (
        f"Topic: '{topic.topic.title}'\n\n"
        f"Content:\n{topic.content_md[:1500]}\n\n"
        "Decide if a Mermaid diagram would meaningfully help a student understand "
        "this topic (e.g. a flowchart for a process, sequence diagram for an "
        "interaction, or concept map for relationships). "
        "If yes, set needs_diagram=true and provide valid Mermaid code in "
        "mermaid_code (include a '---\\ntitle: ...\\n---' frontmatter block) "
        "and a short caption. "
        "If no diagram is needed, set needs_diagram=false."
    )

    result: dict = llm.generate(prompt, system=_SYSTEM, response_schema=_SCHEMA)

    if result.get("needs_diagram") and result.get("mermaid_code"):
        diagrams.append(
            Diagram(
                diagram_id=str(uuid.uuid4()),
                diagram_type="mermaid",
                content=result["mermaid_code"],
                caption=result.get("caption", ""),
            )
        )

    for img in (extracted_images or []):
        diagrams.append(
            Diagram(
                diagram_id=str(uuid.uuid4()),
                diagram_type="extracted_image",
                content=img.file_path,
                caption=img.caption or f"Image from {img.source_location}",
            )
        )

    return diagrams
