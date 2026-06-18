from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from backend.ingestion.models import Document, Section, SourceType

_DEFAULT_MAX_SECTIONS = 16
_WORD_CHUNK_TARGET = 500
_TIME_GAP_THRESHOLD_S = 30.0

# ── Timestamp parsing ────────────────────────────────────────────────────────

_TS_RE = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})\.(\d{3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})\.(\d{3})"
)


def _ts_to_seconds(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


# ── Speaker detection ────────────────────────────────────────────────────────

_VOICE_TAG_RE = re.compile(r"<v\s+([^>]+)>", re.IGNORECASE)
_SPEAKER_PREFIX_RE = re.compile(r"^(Speaker\s*\d+|[A-Z][a-zA-Z\s]{0,30})\s*:\s*", re.MULTILINE)

# ── HTML / formatting cleanup ────────────────────────────────────────────────

_HTML_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")
_CUE_ID_RE = re.compile(r"^\d+\s*$")

# ── Chatter / non-content patterns ───────────────────────────────────────────

_CHATTER_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"^\s*(hi|hello|hey|good morning|good afternoon|good evening)\b.*$",
        r"^\s*can\s+you\s+hear\s+me",
        r"^\s*let\s+me\s+share\s+my\s+screen",
        r"^\s*am\s+i\s+(audible|visible)",
        r"^\s*is\s+my\s+screen\s+visible",
        r"^\s*one\s+(second|moment|sec)\b",
        r"^\s*sorry\s*(,|\s)*(i|my)\s*(was|got)\s*(muted|disconnected)",
        r"^\s*you('re|\s+are)\s+on\s+mute",
        r"^\s*(thanks?|thank\s+you)\s*(for\s+joining|everyone|all)?\s*[.!]?\s*$",
        r"^\s*(bye|goodbye|see\s+you|have\s+a\s+(good|great)\s+(day|evening))\b.*$",
        r"^\s*(okay|ok|alright|sure|yes|yeah|right|mm-hmm|uh-huh)\s*[.!,]?\s*$",
        r"^\s*let('s|\s+us)\s+(wait|give)\s+(for|a)\s+(others|few|moment)",
        r"^\s*(we('ll|\s+will)\s+)?(start|begin)\s+(in\s+a\s+(few|couple)|shortly|soon)",
    ]
]

# ── Topic shift signals ──────────────────────────────────────────────────────

_TOPIC_SHIFT_RE = re.compile(
    r"(?:let(?:'s| us)\s+(?:move on to|talk about|look at|discuss|go (?:over|through))|"
    r"next\s+(?:topic|section|slide|part)|"
    r"now\s+(?:let(?:'s| us)\s+(?:talk|look|discuss|move)|we(?:'ll| will)\s+(?:talk|look|discuss|move))|"
    r"moving\s+(?:on|forward)\s+to|"
    r"the\s+next\s+(?:thing|concept|topic)\s+is)",
    re.IGNORECASE,
)

# ── Q&A detection ────────────────────────────────────────────────────────────

_QUESTION_RE = re.compile(
    r"(?:^|\.\s+)(?:what|how|why|when|where|which|who|can\s+you\s+explain|"
    r"could\s+you\s+(?:explain|clarify|elaborate)|"
    r"is\s+(?:it|that|this)|are\s+(?:there|these|those)|"
    r"do\s+(?:we|you)|does\s+(?:it|this|that))\b.*\?",
    re.IGNORECASE | re.MULTILINE,
)


# ── Data structures ──────────────────────────────────────────────────────────


@dataclass
class _Cue:
    start: float
    end: float
    speaker: str
    text: str
    is_question: bool = False


@dataclass
class _RawSection:
    title: str
    body_parts: list[str] = field(default_factory=list)
    qa_parts: list[str] = field(default_factory=list)
    is_qa: bool = False


# ── Core parsing ─────────────────────────────────────────────────────────────


def parse_vtt(file_path: str, max_sections: int = _DEFAULT_MAX_SECTIONS) -> Document:
    path = Path(file_path)
    text = path.read_text(encoding="utf-8-sig")

    if not text.strip().startswith("WEBVTT"):
        raise ValueError(f"Not a valid WebVTT file: {path.name}")

    cues = _parse_cues(text)
    cues = _strip_chatter(cues)

    if not cues:
        return Document(
            doc_id=str(uuid.uuid4()),
            title=path.stem,
            source_filename=path.name,
            source_type=SourceType.VTT,
            sections=[],
            total_pages=0,
        )

    speaker_names = {c.speaker for c in cues if c.speaker}
    _mark_questions(cues)

    raw_sections = _segment(cues, speaker_names)
    raw_sections = _merge_small_sections(raw_sections)
    raw_sections = raw_sections[:max_sections]

    sections = _build_sections(raw_sections, speaker_names)

    return Document(
        doc_id=str(uuid.uuid4()),
        title=path.stem,
        source_filename=path.name,
        source_type=SourceType.VTT,
        sections=sections,
        total_pages=len(sections),
    )


# ── Cue extraction ───────────────────────────────────────────────────────────


def _parse_cues(text: str) -> list[_Cue]:
    text = _strip_blocks(text, "NOTE")
    text = _strip_blocks(text, "STYLE")
    text = _strip_blocks(text, "REGION")

    cues: list[_Cue] = []
    blocks = re.split(r"\n\s*\n", text)

    for block in blocks:
        block = block.strip()
        if not block or block.startswith("WEBVTT"):
            continue

        ts_match = _TS_RE.search(block)
        if not ts_match:
            continue

        start = _ts_to_seconds(*ts_match.group(1, 2, 3, 4))
        end = _ts_to_seconds(*ts_match.group(5, 6, 7, 8))

        payload_start = ts_match.end()
        payload = block[payload_start:].strip()

        speaker = ""
        voice_match = _VOICE_TAG_RE.search(payload)
        if voice_match:
            speaker = voice_match.group(1).strip()

        if not speaker:
            prefix_match = _SPEAKER_PREFIX_RE.match(payload)
            if prefix_match:
                speaker = prefix_match.group(1).strip()

        clean = _clean_cue_text(payload)
        if clean:
            cues.append(_Cue(start=start, end=end, speaker=speaker, text=clean))

    return cues


def _strip_blocks(text: str, block_type: str) -> str:
    pattern = re.compile(
        rf"^{block_type}\b[^\n]*\n(?:(?!^\s*$).*\n)*",
        re.MULTILINE,
    )
    return pattern.sub("", text)


def _clean_cue_text(text: str) -> str:
    text = _HTML_TAG_RE.sub("", text)
    text = _SPEAKER_PREFIX_RE.sub("", text)
    lines = []
    for line in text.split("\n"):
        line = line.strip()
        if not line or _CUE_ID_RE.match(line):
            continue
        lines.append(line)
    return " ".join(lines)


# ── Chatter filtering ────────────────────────────────────────────────────────


def _strip_chatter(cues: list[_Cue]) -> list[_Cue]:
    result = []
    for cue in cues:
        if any(p.match(cue.text) for p in _CHATTER_PATTERNS):
            continue
        result.append(cue)
    return result


# ── Q&A marking ──────────────────────────────────────────────────────────────


def _mark_questions(cues: list[_Cue]) -> None:
    for cue in cues:
        if _QUESTION_RE.search(cue.text):
            cue.is_question = True


# ── Segmentation ─────────────────────────────────────────────────────────────


def _segment(cues: list[_Cue], speaker_names: set[str]) -> list[_RawSection]:
    if not cues:
        return []

    sections: list[_RawSection] = []
    current = _RawSection(title="")
    topic_counter = 1
    qa_counter = 1
    in_qa_block = False
    qa_answer_seen = False

    for i, cue in enumerate(cues):
        # Detect topic shift signals in the cue text
        topic_match = _TOPIC_SHIFT_RE.search(cue.text)

        # Detect time gap from previous cue
        time_gap = False
        if i > 0:
            gap = cue.start - cues[i - 1].end
            if gap >= _TIME_GAP_THRESHOLD_S:
                time_gap = True

        # Q&A detection: question from one speaker, answer from another
        if cue.is_question and not in_qa_block:
            # Flush current teaching section if it has content
            if current.body_parts:
                if not current.title:
                    current.title = f"Part {topic_counter}"
                    topic_counter += 1
                sections.append(current)

            in_qa_block = True
            qa_answer_seen = False
            current = _RawSection(title=f"Q&A {qa_counter}", is_qa=True)
            current.qa_parts.append(f"**Q:** {cue.text}")
            continue

        if in_qa_block:
            if not cue.is_question:
                if not qa_answer_seen:
                    current.qa_parts.append(f"**A:** {cue.text}")
                    qa_answer_seen = True
                else:
                    # Additional answer continuation
                    current.qa_parts.append(cue.text)

                # Check if next cue starts a new topic or is another question
                if i + 1 < len(cues) and (
                    cues[i + 1].is_question
                    or _TOPIC_SHIFT_RE.search(cues[i + 1].text)
                    or (cues[i + 1].start - cue.end >= _TIME_GAP_THRESHOLD_S)
                ):
                    qa_counter += 1
                    sections.append(current)
                    current = _RawSection(title="")
                    in_qa_block = False
                continue
            else:
                # Another question in the Q&A block — close current, start new
                qa_counter += 1
                sections.append(current)
                current = _RawSection(title=f"Q&A {qa_counter}", is_qa=True)
                current.qa_parts.append(f"**Q:** {cue.text}")
                qa_answer_seen = False
                continue

        # Topic shift or time gap → start new section
        if topic_match or time_gap:
            if current.body_parts:
                if not current.title:
                    current.title = f"Part {topic_counter}"
                    topic_counter += 1
                sections.append(current)

            current = _RawSection(title="")
            if topic_match:
                # Try to extract topic name from the signal
                after = cue.text[topic_match.end():].strip().rstrip(".,;:")
                if after and len(after) < 80:
                    current.title = f"Topic: {after.capitalize()}"
                    continue  # the shift signal itself is consumed
                else:
                    current.title = f"Topic {topic_counter}"

        current.body_parts.append(cue.text)

    # Flush remaining
    if current.body_parts or current.qa_parts:
        if not current.title:
            current.title = f"Part {topic_counter}"
        sections.append(current)

    return sections


def _merge_small_sections(sections: list[_RawSection]) -> list[_RawSection]:
    if len(sections) <= 1:
        return sections

    merged: list[_RawSection] = []
    for sec in sections:
        word_count = sum(len(p.split()) for p in sec.body_parts + sec.qa_parts)
        if merged and not sec.is_qa and word_count < 50 and not merged[-1].is_qa:
            merged[-1].body_parts.extend(sec.body_parts)
            merged[-1].qa_parts.extend(sec.qa_parts)
        else:
            merged.append(sec)

    return merged


# ── Fixed-chunk fallback ─────────────────────────────────────────────────────


def _apply_fixed_chunking(sections: list[_RawSection], max_sections: int) -> list[_RawSection]:
    if len(sections) != 1 or sections[0].is_qa:
        return sections

    text = "\n\n".join(sections[0].body_parts)
    words = text.split()
    if len(words) <= _WORD_CHUNK_TARGET:
        return sections

    chunks: list[_RawSection] = []
    for i in range(0, len(words), _WORD_CHUNK_TARGET):
        chunk_words = words[i : i + _WORD_CHUNK_TARGET]
        part_num = len(chunks) + 1
        chunks.append(
            _RawSection(title=f"Part {part_num}", body_parts=[" ".join(chunk_words)])
        )
        if len(chunks) >= max_sections:
            break

    return chunks


# ── Section building (privacy: strip names) ──────────────────────────────────


def _build_sections(
    raw_sections: list[_RawSection], speaker_names: set[str]
) -> list[Section]:
    # Apply fixed chunking if there's only one big section
    raw_sections = _apply_fixed_chunking(raw_sections, _DEFAULT_MAX_SECTIONS)

    sections: list[Section] = []
    for raw in raw_sections:
        body_text = "\n\n".join(raw.body_parts)

        if raw.qa_parts:
            qa_block = "\n\n".join(raw.qa_parts)
            if body_text:
                body_text = f"{body_text}\n\n---\n\n**Q&A**\n\n{qa_block}"
            else:
                body_text = qa_block

        body_text = _scrub_names(body_text, speaker_names)
        title = _scrub_names(raw.title, speaker_names)

        if not body_text.strip():
            continue

        sections.append(
            Section(
                section_id=str(uuid.uuid4()),
                title=title,
                body=body_text,
                level=1,
            )
        )

    return sections


def _scrub_names(text: str, speaker_names: set[str]) -> str:
    if not speaker_names:
        return text

    sorted_names = sorted(speaker_names, key=len, reverse=True)
    for i, name in enumerate(sorted_names):
        if not name:
            continue
        replacement = "Instructor" if i == 0 else "Participant"
        text = re.sub(re.escape(name), replacement, text, flags=re.IGNORECASE)

    return text
