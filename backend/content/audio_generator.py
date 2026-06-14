from __future__ import annotations

import asyncio
import os
import re

import edge_tts

VOICE = "en-US-AriaNeural"
OUTPUT_DIR = "data/audio"


def generate_audio(
    text: str,
    topic_id: str,
    diagram_caption: str = "",
    diagram_mermaid: str = "",
) -> str:
    """Generate mp3 narration for a topic.

    The audio opens by describing the diagram (so speech and image are connected),
    then continues with the concept explanation.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f"{topic_id}.mp3")

    script = _build_script(text, diagram_caption, diagram_mermaid)
    asyncio.run(_synthesize(script, path))
    return path


def _build_script(text: str, caption: str, mermaid: str) -> str:
    parts = []

    # Describe the diagram before the concept explanation
    if caption or mermaid:
        diagram_description = _describe_diagram(caption, mermaid)
        if diagram_description:
            parts.append(diagram_description)

    parts.append(_strip_markdown(text))
    return "\n\n".join(p for p in parts if p.strip())


def _describe_diagram(caption: str, mermaid: str) -> str:
    """Turn a Mermaid diagram into a spoken description."""
    lines = []

    if caption:
        lines.append(f"Let us look at the diagram. {caption}.")

    # Extract node labels and edges from Mermaid flowchart syntax
    if mermaid:
        node_labels = re.findall(r'\[([^\]]+)\]', mermaid)
        # Clean up labels: remove HTML entities, extra whitespace
        node_labels = [re.sub(r'#\w+;', '', lbl).strip() for lbl in node_labels]
        node_labels = [lbl for lbl in node_labels if lbl and len(lbl) > 1]

        if node_labels:
            unique = list(dict.fromkeys(node_labels))  # preserve order, deduplicate
            if len(unique) == 1:
                lines.append(f"The diagram shows: {unique[0]}.")
            elif len(unique) == 2:
                lines.append(f"The diagram shows how {unique[0]} connects to {unique[1]}.")
            else:
                middle = ", ".join(unique[:-1])
                lines.append(
                    f"The diagram traces a flow from {unique[0]}, through {middle}, to {unique[-1]}."
                )

    return " ".join(lines)


async def _synthesize(text: str, output_path: str) -> None:
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(output_path)


def _strip_markdown(text: str) -> str:
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`[^`]+`", "", text)
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"#{1,6}\s*", "", text)
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", text)
    text = re.sub(r"^[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^>\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
