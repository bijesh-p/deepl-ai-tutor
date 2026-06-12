from __future__ import annotations

import uuid
from datetime import datetime, timezone

from backend.content.content_enricher import enrich
from backend.content.diagram_generator import generate_diagrams
from backend.content.inline_question_gen import generate_inline_questions
from backend.content.llm_client import LLMClient
from backend.content.models import LearningModule
from backend.content.topic_decomposer import decompose, _format_sections
from backend.ingestion.models import Document


def run_pipeline(doc: Document, llm: LLMClient) -> LearningModule:
    """Transform a parsed Document into a LearningModule.

    Caches the full document text across all enrichment calls to reduce
    token costs on repeated LLM invocations.
    """
    cached_blocks = llm.make_cached_document_blocks(_format_sections(doc))

    topics = decompose(doc, llm)

    enriched_topics = []
    for topic in topics:
        source_text = _collect_source_text(doc, topic.source_section_ids)
        enriched = enrich(topic, source_text, llm, cached_blocks=cached_blocks)
        enriched.diagrams = generate_diagrams(enriched, llm)
        enriched.inline_questions = generate_inline_questions(enriched, llm)
        enriched_topics.append(enriched)

    return LearningModule(
        module_id=str(uuid.uuid4()),
        title=doc.title,
        source_doc_id=doc.doc_id,
        topics=enriched_topics,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _collect_source_text(doc: Document, section_ids: list[str]) -> str:
    id_set = set(section_ids)
    parts = [s.body for s in doc.sections if s.section_id in id_set]
    return "\n\n".join(parts)
