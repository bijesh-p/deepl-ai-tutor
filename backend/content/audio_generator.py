from __future__ import annotations

import asyncio
import os
import re

import edge_tts

VOICE = "en-US-AriaNeural"
OUTPUT_DIR = "data/audio"

_DIAGNOSTIC_INTRO = (
    "Before we begin, I have a quick question to understand where you are with this topic. "
    "Don't worry — there are no right or wrong answers here. "
    "This just helps me pitch the explanation at the right level for you. "
    "Think about it for a moment, then we will dive in."
)

_DIAGNOSTIC_AUDIO_DIR = "data/audio"


def generate_diagnostic_audio(topic_title: str = "", backend: str = "edge-tts") -> str:
    """Generate TTS for the diagnostic framing message — no LLM needed.

    Called immediately after PDF parsing so audio is ready when the student
    lands on the diagnostic page (~3s, pure TTS).
    """
    os.makedirs(_DIAGNOSTIC_AUDIO_DIR, exist_ok=True)
    ext = "wav" if backend == "kokoro" else "mp3"
    path = os.path.join(_DIAGNOSTIC_AUDIO_DIR, f"diagnostic_intro.{ext}")

    intro = _DIAGNOSTIC_INTRO
    if topic_title:
        intro = f"Welcome. We will be exploring: {topic_title}. " + intro

    _synthesize(intro, path, backend)
    return path


def generate_audio(
    text: str,
    topic_id: str,
    diagram_caption: str = "",
    diagram_mermaid: str = "",
    bullets: list[str] | None = None,
    topic_title: str = "",
    backend: str = "edge-tts",
) -> str:
    """Generate narration for a topic.

    Describes the slide anchor (diagram or bullet points) then continues
    with the explanation.  Output format is mp3 for edge-tts, wav for kokoro.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ext = "wav" if backend == "kokoro" else "mp3"
    path = os.path.join(OUTPUT_DIR, f"{topic_id}.{ext}")

    script = _build_script(text, diagram_caption, diagram_mermaid, bullets or [], topic_title)
    _synthesize(script, path, backend)
    return path


def _synthesize(text: str, output_path: str, backend: str) -> None:
    if backend == "kokoro":
        _synthesize_kokoro(text, output_path)
    else:
        asyncio.run(_synthesize_edge_tts(text, output_path))


def _synthesize_kokoro(text: str, output_path: str) -> None:
    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline

    pipeline = KPipeline(lang_code="a")  # 'a' = American English
    chunks = []
    for _, _, audio in pipeline(text, voice="af_heart", speed=1.0):
        chunks.append(audio)
    combined = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)
    sf.write(output_path, combined, 24000)


async def _synthesize_edge_tts(text: str, output_path: str) -> None:
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(output_path)


def _build_script(
    text: str,
    caption: str,
    mermaid: str,
    bullets: list[str],
    topic_title: str,
) -> str:
    parts: list[str] = []

    # 1. Topic introduction
    if topic_title:
        parts.append(f"Now let's explore: {topic_title}.")

    # 2. Slide anchor — diagram or bullets
    if caption or mermaid:
        diagram_description = _describe_diagram(caption, mermaid)
        if diagram_description:
            parts.append(diagram_description)
    elif bullets:
        parts.append(_describe_bullets(bullets))

    # 3. Main explanation
    parts.append(_strip_markdown(text))

    return "\n\n".join(p for p in parts if p.strip())


def _describe_diagram(caption: str, mermaid: str) -> str:
    lines: list[str] = []

    if caption:
        lines.append(f"Let us look at the diagram. {caption}.")

    if mermaid:
        node_labels = re.findall(r'\[([^\]]+)\]', mermaid)
        node_labels = [re.sub(r'#\w+;', '', lbl).strip() for lbl in node_labels]
        node_labels = [lbl for lbl in node_labels if lbl and len(lbl) > 1]

        if node_labels:
            unique = list(dict.fromkeys(node_labels))
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


def _describe_bullets(bullets: list[str]) -> str:
    if not bullets:
        return ""
    intro = "Here are the key ideas for this topic."
    items = " ".join(f"Point {i + 1}: {b}" for i, b in enumerate(bullets))
    return f"{intro} {items}"


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
