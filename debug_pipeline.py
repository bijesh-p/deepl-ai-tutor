"""End-to-end pipeline debug script — uses a tiny 2-page in-memory PDF."""
from __future__ import annotations

import json
import tempfile
import traceback
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

import fitz  # PyMuPDF


def make_two_page_pdf() -> str:
    """Write a 2-page PDF to a temp file and return its path."""
    doc = fitz.open()

    pages = [
        (
            "What is Deep Learning",
            (
                "Deep learning is a branch of machine learning that uses neural networks "
                "with many layers (hence 'deep') to learn representations of data. "
                "It powers modern applications such as image recognition, speech-to-text, "
                "and large language models."
            ),
        ),
        (
            "Convolutional Neural Networks",
            (
                "A Convolutional Neural Network (CNN) applies learnable filters across an "
                "input image to detect edges, textures, and shapes. Pooling layers reduce "
                "spatial dimensions. CNNs are the backbone of most computer-vision systems."
            ),
        ),
    ]

    for title, body in pages:
        page = doc.new_page()
        page.insert_text((50, 72), title, fontsize=16)
        tw = fitz.TextWriter(page.rect)
        tw.append((50, 120), body, fontsize=11)
        tw.write_text(page)

    doc.set_toc([[1, pages[0][0], 1], [1, pages[1][0], 2]])
    doc.set_metadata({"title": "Deep Learning Overview"})

    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp_path = tmp.name
    tmp.close()  # must close on Windows before another process writes to it
    doc.save(tmp_path)
    doc.close()
    print(f"[PDF] Written to {tmp_path}")
    return tmp_path


def run():
    print("=" * 60)
    print("AI Tutor — end-to-end pipeline debug")
    print("=" * 60)

    # ── Step 1: Parse PDF ──────────────────────────────────────
    print("\n[1/5] Parsing PDF…")
    try:
        pdf_path = make_two_page_pdf()
        from ingestion.pdf_parser import parse_pdf
        doc = parse_pdf(pdf_path)
        print(f"  OK  title={doc.title!r}  sections={len(doc.sections)}  pages={doc.total_pages}")
        for s in doc.sections:
            print(f"       section: {s.title!r}  body_len={len(s.body)}")
    except Exception:
        print("  FAIL")
        traceback.print_exc()
        return

    # ── Step 2: LLM client ─────────────────────────────────────
    print("\n[2/5] Creating LLM client…")
    try:
        from content.llm_client import LLMClient
        llm = LLMClient()
        print(f"  OK  provider={llm.provider!r}  model={llm.model!r}  key={'set' if llm.api_key else 'MISSING'}")
    except Exception:
        print("  FAIL")
        traceback.print_exc()
        return

    # ── Step 3: Topic decomposition ────────────────────────────
    print("\n[3/5] Decomposing topics…")
    try:
        from content.topic_decomposer import decompose, _format_sections
        cached_blocks = llm.make_cached_document_blocks(_format_sections(doc))
        topics = decompose(doc, llm)
        print(f"  OK  topics={len(topics)}")
        for t in topics:
            print(f"       topic: {t.title!r}  source_ids={t.source_section_ids}")
    except Exception:
        print("  FAIL")
        traceback.print_exc()
        return

    # ── Step 4: Enrich each topic ──────────────────────────────
    print("\n[4/5] Enriching topics…")
    from content.content_enricher import enrich
    from content.diagram_generator import generate_diagrams
    from content.inline_question_gen import generate_inline_questions
    from content.models import LearningModule
    import uuid
    from datetime import datetime, timezone

    enriched_topics = []
    for i, topic in enumerate(topics, 1):
        print(f"  [{i}/{len(topics)}] enriching {topic.title!r}…")
        try:
            source_text = "\n\n".join(
                s.body for s in doc.sections if s.section_id in set(topic.source_section_ids)
            )
            enriched = enrich(topic, source_text, llm, cached_blocks=cached_blocks)
            print(f"         enrich OK  content_md_len={len(enriched.content_md)}  takeaways={len(enriched.key_takeaways)}")

            enriched.diagrams = generate_diagrams(enriched, llm)
            print(f"         diagrams OK  count={len(enriched.diagrams)}")

            enriched.inline_questions = generate_inline_questions(enriched, llm)
            print(f"         inline_questions OK  count={len(enriched.inline_questions)}")

            enriched_topics.append(enriched)
        except Exception:
            print(f"         FAIL on topic {topic.title!r}")
            traceback.print_exc()
            return

    module = LearningModule(
        module_id=str(uuid.uuid4()),
        title=doc.title,
        source_doc_id=doc.doc_id,
        topics=enriched_topics,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    print(f"  OK  module built  topics={len(module.topics)}")

    # ── Step 5: Question bank ──────────────────────────────────
    print("\n[5/5] Generating question bank…")
    try:
        from quiz.question_bank import generate_question_bank
        bank = generate_question_bank(module, llm)
        print(f"  OK  questions={len(bank.questions)}")
        by_diff: dict[str, int] = {}
        for q in bank.questions:
            by_diff[q.difficulty] = by_diff.get(q.difficulty, 0) + 1
        print(f"       difficulty breakdown: {by_diff}")
    except Exception:
        print("  FAIL")
        traceback.print_exc()
        return

    print("\n" + "=" * 60)
    print("ALL STEPS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    run()
