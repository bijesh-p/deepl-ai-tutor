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


def generate_diagnostic_audio(topic_title: str = "") -> str:
    """Generate TTS for the diagnostic framing message — no LLM needed.

    Called immediately after PDF parsing so audio is ready when the student
    lands on the diagnostic page (~3s, pure TTS).
    """
    os.makedirs(_DIAGNOSTIC_AUDIO_DIR, exist_ok=True)
    path = os.path.join(_DIAGNOSTIC_AUDIO_DIR, "diagnostic_intro.mp3")

    intro = _DIAGNOSTIC_INTRO
    if topic_title:
        intro = f"Welcome. We will be exploring: {topic_title}. " + intro

    asyncio.run(_synthesize(_strip_emoji(intro), path))
    return path


def generate_audio(
    text: str,
    topic_id: str,
    bullets: list[str] | None = None,
    topic_title: str = "",
) -> str:
    """Generate mp3 narration for a topic.

    Opens with a topic introduction, then describes the slide anchor (bullet
    points only — diagrams are not narrated, just shown), then continues
    with the explanation.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f"{topic_id}.mp3")

    script = _build_script(text, bullets or [], topic_title)
    asyncio.run(_synthesize(script, path))
    return path


def _build_script(
    text: str,
    bullets: list[str],
    topic_title: str,
) -> str:
    parts: list[str] = []

    # 1. Topic introduction
    if topic_title:
        parts.append(f"Now let's explore: {topic_title}.")

    # 2. Slide anchor — bullets only (diagrams are shown, not narrated)
    if bullets:
        parts.append(_describe_bullets(bullets))

    # 3. Main explanation
    parts.append(_strip_markdown(text))

    script = "\n\n".join(p for p in parts if p.strip())
    return _strip_emoji(script)


def _describe_bullets(bullets: list[str]) -> str:
    if not bullets:
        return ""
    intro = "Here are the key ideas for this topic."
    items = " ".join(f"Point {i + 1}: {b}" for i, b in enumerate(bullets))
    return f"{intro} {items}"


async def _synthesize(text: str, output_path: str) -> None:
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(output_path)


_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"  # symbols, pictographs, emoticons, supplemental symbols
    "\U00002600-\U000027BF"  # misc symbols, dingbats
    "\U0000FE0E-\U0000FE0F"  # text/emoji variation selectors
    "\U0000200D"             # zero-width joiner (compound emoji)
    "]+"
)


def _strip_emoji(text: str) -> str:
    """Remove emoji so TTS engines don't speak their alt-text description
    (e.g. a colored-circle emoji becoming the spoken words "green circle")."""
    return _EMOJI_RE.sub("", text)


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
