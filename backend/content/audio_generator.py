from __future__ import annotations

import asyncio
import os
import re

import edge_tts

VOICE = "en-US-AriaNeural"
OUTPUT_DIR = "data/audio"


def generate_audio(text: str, topic_id: str) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f"{topic_id}.mp3")
    clean = _strip_markdown(text)
    asyncio.run(_synthesize(clean, path))
    return path


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
