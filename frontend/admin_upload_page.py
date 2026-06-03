from __future__ import annotations

import json
import os
import tempfile
import uuid
from dataclasses import asdict
from datetime import datetime, timezone

import streamlit as st

from analytics.db import get_db
from analytics.persistence import save_module
from content.content_enricher import enrich
from content.diagram_generator import generate_diagrams
from content.inline_question_gen import generate_inline_questions
from content.llm_client import LLMClient
from content.models import LearningModule
from content.topic_decomposer import decompose, _format_sections
from ingestion.pdf_parser import parse_pdf
from quiz.models import QuestionBank, QuizQuestion
from quiz.question_bank import generate_question_bank


def render_admin_upload_page() -> None:
    if st.session_state.get("role") != "admin":
        st.session_state["page"] = "login"
        st.rerun()

    st.title("Admin — Generate Learning Module")
    st.caption(f"Logged in as **{st.session_state.get('username', '')}** (admin)")

    col1, col2 = st.columns([6, 1])
    with col2:
        if st.button("Module Library →"):
            st.session_state["page"] = "module_library"
            st.rerun()

    uploaded = st.file_uploader("Upload a PDF document (first 4 pages will be used)", type=["pdf"])

    if not st.button("Generate Learning Module", disabled=uploaded is None):
        return

    try:
        with st.status("Processing document…", expanded=True) as status:

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

            st.write("🤖 Step 2 / 6 — Connecting to Anthropic Claude…")
            llm = LLMClient()
            st.write(f"✅ Connected — model: `{llm.model}`")

            st.write("🧠 Step 3 / 6 — Decomposing document into learning topics…")
            cached_blocks = llm.make_cached_document_blocks(_format_sections(doc))
            topics = decompose(doc, llm)
            st.write(f"✅ Identified **{len(topics)} topic(s)**: {', '.join(t.title for t in topics)}")

            st.write(f"✍️ Step 4 / 6 — Enriching {len(topics)} topic(s) with AI…")
            enriched_topics = []
            for i, topic in enumerate(topics, 1):
                st.write(f"   ↳ Topic {i}/{len(topics)}: **{topic.title}**")
                source_text = "\n\n".join(
                    s.body for s in doc.sections if s.section_id in set(topic.source_section_ids)
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

            st.write("📝 Step 5 / 6 — Generating quiz question bank…")
            bank = generate_question_bank(module, llm)
            st.write(f"✅ Question bank ready — **{len(bank.questions)} questions**")

            st.write("💾 Step 6 / 6 — Saving to database…")
            db = get_db()
            save_module(
                module_id=module.module_id,
                title=module.title,
                source_filename=doc.source_filename,
                module_json=module.to_json(),
                question_bank_json=json.dumps(_bank_to_dict(bank)),
                created_by=st.session_state["user_id"],
                db=db,
            )
            st.write("✅ Module published to library!")

            status.update(label=f"✅ **{module.title}** is now available in the module library.", state="complete")

    except Exception as exc:
        st.error(f"❌ Error: {exc}")
        st.exception(exc)
        return

    if st.button("Go to Module Library", type="primary"):
        st.session_state["page"] = "module_library"
        st.rerun()


def _bank_to_dict(bank: QuestionBank) -> dict:
    return {"module_id": bank.module_id, "questions": [asdict(q) for q in bank.questions]}
