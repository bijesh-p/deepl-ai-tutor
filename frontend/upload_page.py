from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import asdict
from datetime import datetime, timezone

import streamlit as st

from backend.analytics.db import get_db
from backend.analytics.persistence import save_module, save_user
from backend.content.content_enricher import enrich
from backend.content.diagram_generator import generate_diagrams
from backend.content.inline_question_gen import generate_inline_questions
from backend.content.llm_client import LLMClient
from backend.content.models import LearningModule
from backend.content.topic_decomposer import decompose, _format_sections
from backend.ingestion.pdf_parser import parse_pdf
from backend.quiz.question_bank import generate_question_bank


def render_upload_page() -> None:
    st.title("AI Tutor")
    st.subheader("Transform any PDF into an interactive learning module")

    username = st.text_input("Your name (used for analytics)", placeholder="e.g. Alice")
    uploaded = st.file_uploader("Upload a PDF document", type=["pdf"])

    # Show what's still needed before the button enables
    missing = []
    if not username:
        missing.append("enter your name")
    if not uploaded:
        missing.append("upload a PDF")
    if missing:
        st.caption(f"To enable: {' and '.join(missing)}")

    if not st.button("Generate Learning Module", disabled=bool(missing)):
        return

    if not username.strip():
        st.error("Please enter your name.")
        return

    module = None
    bank = None
    user_id = None

    try:
        with st.status("Processing your document…", expanded=True) as status:

            # ── Step 1: Parse PDF ──────────────────────────────────────────
            st.write("📄 Step 1 / 6 — Parsing PDF (first 4 pages)…")
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(uploaded.read())
                tmp_path = tmp.name
            try:
                doc = parse_pdf(tmp_path, max_pages=4)
            finally:
                os.unlink(tmp_path)
            st.write(
                f"✅ Parsed **{doc.title}** — "
                f"{len(doc.sections)} section(s), {doc.total_pages} page(s) used"
            )

            # ── Step 2: Connect to LLM ─────────────────────────────────────
            st.write("🤖 Step 2 / 6 — Connecting to Anthropic Claude…")
            llm = LLMClient()
            st.write(f"✅ Connected — model: `{llm.model}`")

            # ── Step 3: Decompose topics ───────────────────────────────────
            st.write("🧠 Step 3 / 6 — Decomposing document into learning topics…")
            cached_blocks = llm.make_cached_document_blocks(_format_sections(doc))
            topics = decompose(doc, llm)
            topic_names = ", ".join(f"*{t.title}*" for t in topics)
            st.write(f"✅ Identified **{len(topics)} topic(s)**: {topic_names}")

            # ── Step 4: Enrich each topic ──────────────────────────────────
            st.write(f"✍️ Step 4 / 6 — Enriching {len(topics)} topic(s) with AI…")
            enriched_topics = []
            for i, topic in enumerate(topics, 1):
                st.write(f"   ↳ Topic {i}/{len(topics)}: **{topic.title}**")
                source_text = "\n\n".join(
                    s.body
                    for s in doc.sections
                    if s.section_id in set(topic.source_section_ids)
                )
                enriched = enrich(topic, source_text, llm, cached_blocks=cached_blocks)
                enriched.diagrams = generate_diagrams(enriched, llm)
                enriched.inline_questions = generate_inline_questions(enriched, llm)
                enriched_topics.append(enriched)
                st.write(
                    f"      ✅ {len(enriched.diagrams)} diagram(s), "
                    f"{len(enriched.inline_questions)} inline question(s)"
                )

            module = LearningModule(
                module_id=str(uuid.uuid4()),
                title=doc.title,
                source_doc_id=doc.doc_id,
                topics=enriched_topics,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            st.write(f"✅ Learning module built — **{len(enriched_topics)} topics**")

            # ── Step 5: Question bank ──────────────────────────────────────
            st.write("📝 Step 5 / 6 — Generating quiz question bank…")
            bank = generate_question_bank(module, llm)
            st.write(f"✅ Question bank ready — **{len(bank.questions)} questions**")

            # ── Step 6: Persist ────────────────────────────────────────────
            st.write("💾 Step 6 / 6 — Saving to database…")
            db = get_db()
            user_id = save_user(username.strip(), db=db)
            save_module(
                module_id=module.module_id,
                title=module.title,
                source_filename=doc.source_filename,
                module_json=module.to_json(),
                question_bank_json=json.dumps(_bank_to_dict(bank)),
                created_by=user_id,
                db=db,
            )
            st.write("✅ Saved!")

            status.update(label="✅ Module ready! Loading learning view…", state="complete")

    except Exception as exc:
        st.error(f"❌ Error: {exc}")
        st.exception(exc)
        return

    st.session_state["module"] = module
    st.session_state["bank"] = bank
    st.session_state["user_id"] = user_id
    st.session_state["username"] = username.strip()
    st.session_state["page"] = "learn"
    st.rerun()


def _bank_to_dict(bank) -> dict:
    return {"module_id": bank.module_id, "questions": [asdict(q) for q in bank.questions]}
