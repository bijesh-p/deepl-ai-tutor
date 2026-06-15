"""Sliding-window content pipeline.

Reads the document in ~500-word chunks. After each chunk, an LLM call
decides whether the accumulated text is enough to teach one focused concept
(≥2 minutes of material). If yes, the concept is immediately enriched and
published to progress["enriched_topics"]. If no, the next chunk is merged
in and the assessment is retried.

This eliminates the decompose step: the first slide is ready after ~2 LLM
calls (assess + enrich) with no need to read the whole document first.
"""
from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from backend.content.models import EnrichedTopic, Topic
from backend.ingestion.models import Document

CHUNK_WORDS = 200

# ---------------------------------------------------------------------------
# Assessment prompt / schema
# ---------------------------------------------------------------------------

MAX_ACCUMULATE_WORDS = 500  # force-publish after this many words even if not assessed presentable

_ASSESS_SYSTEM = (
    "You are an instructional designer reading a section of a document. "
    "Decide: does the accumulated text introduce at least ONE concept, process, "
    "technique, or idea that could be explained to a student? "
    "Return is_presentable=true if there is any substantive explanatory content — "
    "even a single well-explained idea qualifies. "
    "Only return false if the text is purely a table of contents, index, "
    "reference list, or bare headings with no explanatory body text at all."
)

_ASSESS_SCHEMA = {
    "name": "assess_chunk",
    "description": "Assess whether the accumulated document text is presentable as one learning concept.",
    "input_schema": {
        "type": "object",
        "properties": {
            "is_presentable": {
                "type": "boolean",
                "description": "True if the text can sustain ≥2 min of teaching.",
            },
            "concept_title": {
                "type": "string",
                "description": "Short title for the concept (empty string if not presentable).",
            },
            "concept_summary": {
                "type": "string",
                "description": "1-2 sentence summary of the concept (empty if not presentable).",
            },
            "reason": {
                "type": "string",
                "description": "Brief explanation of the decision.",
            },
        },
        "required": ["is_presentable", "concept_title", "concept_summary", "reason"],
    },
}

_ASSESS_PROMPT_TMPL = (
    "Document chunk ({n_words} words accumulated so far):\n\n"
    "{text}\n\n"
    "Assess whether this contains a self-contained, teachable concept."
)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_sliding_pipeline(
    doc: Document,
    llm,
    progress: dict,
    abort_event: threading.Event,
    tracer,
    chunk_words: int = CHUNK_WORDS,
) -> list[EnrichedTopic]:
    """Process the document in sliding windows, publishing slides as they emerge.

    Sets progress["ready"] = True as soon as the first slide is published so
    the UI can redirect to the tutor room. Continues in the background for
    all remaining chunks.

    Returns the final list of published EnrichedTopics.
    """
    all_words = _doc_words(doc)
    accumulated: list[tuple[str, str]] = []   # (word, section_id)
    published: list[EnrichedTopic] = []
    idx = 0
    total_words = len(all_words)
    module_id = progress.get("module_id", "")

    for start in range(0, total_words, chunk_words):
        if abort_event.is_set():
            break

        chunk = all_words[start : start + chunk_words]
        accumulated += chunk

        progress["detail"] = (
            f"Reading document... {start + len(chunk)}/{total_words} words processed"
        )

        force_publish = len(accumulated) >= MAX_ACCUMULATE_WORDS
        assessment = _assess(llm, accumulated)

        if assessment.get("is_presentable") or force_publish:
            if force_publish and not assessment.get("is_presentable"):
                # Override: synthesise a generic title from the accumulated text
                assessment = {
                    "is_presentable": True,
                    "concept_title": assessment.get("concept_title") or f"Concept {idx + 1}",
                    "concept_summary": assessment.get("concept_summary") or "Key ideas from this section of the document.",
                    "reason": "force-published after max accumulation limit",
                }
            topic = _make_topic(assessment, accumulated, idx)
            source_text = " ".join(w for w, _ in accumulated)

            enriched = _enrich_one(
                topic, source_text, llm, tracer, abort_event,
                audio_enabled=progress.get("audio_enabled", True),
            )
            if enriched is not None:
                published.append(enriched)
                _store_in_vector_db(enriched, module_id)
                progress["enriched_topics"] = list(published)
                progress["topics_enriched"] = len(published)
                progress["current_topic"] = enriched.topic.title
                progress["detail"] = f"Slide {len(published)} ready: {enriched.topic.title}"

                if len(published) == 1:
                    progress["ready"] = True   # triggers redirect to tutor room

                idx += 1

            accumulated = []   # reset — next chunk starts fresh

    # Handle leftover text at end of document
    if accumulated and not abort_event.is_set():
        assessment = _assess(llm, accumulated)
        # Always publish leftover if nothing was published yet — last resort fallback
        force = not published
        if assessment.get("is_presentable") or force:
            if force and not assessment.get("is_presentable"):
                assessment = {
                    "is_presentable": True,
                    "concept_title": assessment.get("concept_title") or f"Concept {idx + 1}",
                    "concept_summary": assessment.get("concept_summary") or "Key ideas from this document.",
                    "reason": "fallback: only content available",
                }
            topic = _make_topic(assessment, accumulated, idx)
            source_text = " ".join(w for w, _ in accumulated)
            enriched = _enrich_one(
                topic, source_text, llm, tracer, abort_event,
                audio_enabled=progress.get("audio_enabled", True),
            )
            if enriched is not None:
                published.append(enriched)
                _store_in_vector_db(enriched, module_id)
                progress["enriched_topics"] = list(published)
                progress["topics_enriched"] = len(published)
                if len(published) == 1:
                    progress["ready"] = True

    progress["total_topics"] = len(published)
    return published


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _store_in_vector_db(enriched: EnrichedTopic, module_id: str) -> None:
    """Upsert the enriched topic's content into ChromaDB via storage_server.

    Non-fatal: semantic search is a supporting feature, so any failure here
    must not break slide publishing.
    """
    try:
        from backend.core.mcp_client import get_client

        topic = enriched.topic
        get_client("storage_server").call(
            "upsert_to_vector_db",
            documents=[enriched.content_md],
            ids=[f"{module_id}:{topic.topic_id}"],
            metadatas=[{
                "module_id": module_id,
                "topic_id": topic.topic_id,
                "title": topic.title,
                "order": topic.order,
            }],
        )
    except Exception as exc:
        print(f"[sliding_pipeline] _store_in_vector_db error ({type(exc).__name__}): {exc}")


def _doc_words(doc: Document) -> list[tuple[str, str]]:
    """Return list of (word, section_id) from all sections in reading order."""
    words: list[tuple[str, str]] = []
    for s in doc.sections:
        for w in s.body.split():
            words.append((w, s.section_id))
    return words


def _assess(llm, accumulated: list[tuple[str, str]]) -> dict:
    """Ask the LLM whether accumulated text is presentable as one concept."""
    import traceback
    text = " ".join(w for w, _ in accumulated)
    try:
        result = llm.generate(
            prompt=_ASSESS_PROMPT_TMPL.format(n_words=len(accumulated), text=text),
            system=_ASSESS_SYSTEM,
            tool_schema=_ASSESS_SCHEMA,
        )
        return result if isinstance(result, dict) else {"is_presentable": False, "concept_title": "", "concept_summary": "", "reason": "unexpected response format"}
    except Exception as exc:
        print(f"[sliding_pipeline] _assess error ({type(exc).__name__}): {exc}")
        traceback.print_exc()
        return {"is_presentable": False, "concept_title": "", "concept_summary": "", "reason": f"error: {exc}"}


def _make_topic(assessment: dict, accumulated: list[tuple[str, str]], idx: int) -> Topic:
    """Create a Topic from an assess_chunk result."""
    # Preserve order, deduplicate section ids
    seen: set[str] = set()
    section_ids: list[str] = []
    for _, sid in accumulated:
        if sid not in seen:
            seen.add(sid)
            section_ids.append(sid)

    return Topic(
        topic_id=str(uuid.uuid4()),
        title=assessment.get("concept_title", f"Concept {idx + 1}"),
        summary=assessment.get("concept_summary", ""),
        source_section_ids=section_ids,
        order=idx,
    )


def _enrich_one(
    topic: Topic,
    source_text: str,
    llm,
    tracer,
    abort_event: threading.Event,
    audio_enabled: bool = True,
) -> EnrichedTopic | None:
    """Enrich a single topic using a diagram-first approach.

    Order:
      1. Generate slide anchor (diagram or bullet fallback) from source text
      2. Enrich — write explanation anchored to the visual
      3. Generate inline questions from enriched content
      4. Generate audio (diagnostic intro + anchor narration + explanation)
    """
    from backend.content.audio_generator import generate_audio
    from backend.content.content_enricher import enrich
    from backend.content.diagram_generator import generate_slide_anchor
    from backend.content.inline_question_gen import generate_inline_questions

    if abort_event.is_set():
        return None

    # Step 1 — anchor first (diagram or bullet fallback)
    with tracer.start_as_current_span(
        "sliding.anchor", attributes={"topic.title": topic.title}
    ):
        anchor = generate_slide_anchor(source_text, topic, llm)

    if abort_event.is_set():
        return None

    # Step 2 — explanation grounded in the anchor
    with tracer.start_as_current_span(
        "sliding.enrich", attributes={"topic.title": topic.title}
    ):
        enriched = enrich(topic, source_text, llm, anchor=anchor)

    # Attach anchor to enriched topic
    if anchor.has_diagram:
        enriched.diagrams = [anchor.diagram]
    else:
        # Prepend bullets into content_md so UI can render them
        enriched.content_md = f"{anchor.bullets_md()}\n\n{enriched.content_md}"
        enriched.diagrams = []

    if abort_event.is_set():
        return None

    # Steps 3 + 4 — questions and audio in parallel (neither depends on the other)
    diagram = enriched.diagrams[0] if enriched.diagrams else None

    def _gen_questions():
        try:
            return generate_inline_questions(enriched, llm)
        except Exception:
            return []

    def _gen_audio():
        try:
            with tracer.start_as_current_span(
                "sliding.audio", attributes={"topic.title": topic.title}
            ):
                return generate_audio(
                    enriched.content_md,
                    topic.topic_id,
                    diagram_caption=diagram.caption if diagram else "",
                    diagram_mermaid=diagram.content if diagram else "",
                    bullets=anchor.bullets if not anchor.has_diagram else [],
                    topic_title=topic.title,
                )
        except Exception:
            return ""

    if audio_enabled:
        with ThreadPoolExecutor(max_workers=2) as ex:
            fut_qs = ex.submit(_gen_questions)
            fut_audio = ex.submit(_gen_audio)
            enriched.inline_questions = fut_qs.result()
            enriched.audio_path = fut_audio.result()
    else:
        enriched.inline_questions = _gen_questions()
        enriched.audio_path = ""

    return enriched
