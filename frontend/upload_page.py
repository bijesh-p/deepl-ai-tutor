from __future__ import annotations

import os
import tempfile
from pathlib import Path

import streamlit as st

from content.content_enricher import enrich
from content.diagram_generator import generate_diagrams
from content.inline_question_gen import generate_inline_questions
from content.llm_client import LLMClient, Provider
from content.models import LearningModule
from content.topic_decomposer import decompose
from ingestion.pdf_parser import parse_pdf
from quiz.question_bank import generate_question_bank
from analytics.persistence import save_user, save_module

import uuid
from datetime import datetime, timezone


def _get_llm() -> LLMClient:
    provider_str = os.environ.get("AI_TUTOR_LLM_PROVIDER", "anthropic").lower()
    model = os.environ.get("AI_TUTOR_LLM_MODEL", "claude-opus-4-8")
    if provider_str == "portkey":
        return LLMClient(
            provider=Provider.PORTKEY,
            api_key=os.environ["AI_TUTOR_PORTKEY_API_KEY"],
            model=model,
            portkey_virtual_key=os.environ["AI_TUTOR_PORTKEY_VIRTUAL_KEY"],
        )
    return LLMClient(
        provider=Provider.ANTHROPIC,
        api_key=os.environ["AI_TUTOR_LLM_API_KEY"],
        model=model,
    )


def render_upload_page() -> None:
    st.title("AI Tutor")
    st.subheader("Transform any document into an interactive learning module")

    st.markdown("---")

    username = st.text_input(
        "Your name",
        placeholder="Enter your name to track your quiz scores",
    )

    uploaded_file = st.file_uploader(
        "Upload a document",
        type=["pdf"],
        help="PDF support is available now. PPTX and DOCX coming soon.",
    )

    if uploaded_file is None:
        st.info("Upload a PDF to get started.")
        return

    if st.button("Generate Learning Module", type="primary", disabled=not username):
        if not username.strip():
            st.warning("Please enter your name before generating a module.")
            return

        _run_pipeline(uploaded_file, username.strip())


def _run_pipeline(uploaded_file, username: str) -> None:
    with st.status("Processing your document...", expanded=True) as status:
        # Save upload to a temp file
        st.write("Saving uploaded file...")
        suffix = Path(uploaded_file.name).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded_file.getbuffer())
            tmp_path = tmp.name

        try:
            st.write("Parsing document...")
            upload_dir = os.environ.get("AI_TUTOR_UPLOAD_DIR", "data/uploads")
            doc = parse_pdf(tmp_path, upload_dir=upload_dir)
            doc.source_filename = uploaded_file.name

            st.write(f"Extracted {len(doc.sections)} sections. Connecting to LLM...")
            llm = _get_llm()

            st.write("Decomposing into topics...")
            topics = decompose(doc, llm)

            enriched_topics = []
            for i, topic in enumerate(topics, 1):
                st.write(f"Enriching topic {i}/{len(topics)}: {topic.title}")
                et = enrich(topic, doc, llm)
                # Attach extracted images from source sections
                section_map = {s.section_id: s for s in doc.sections}
                extracted = []
                for sid in topic.source_section_ids:
                    sec = section_map.get(sid)
                    if sec:
                        extracted.extend(sec.images)
                et.diagrams = generate_diagrams(et, llm, extracted_images=extracted)
                et.inline_questions = generate_inline_questions(et, llm)
                enriched_topics.append(et)

            module = LearningModule(
                module_id=str(uuid.uuid4()),
                title=doc.title,
                source_doc_id=doc.doc_id,
                topics=enriched_topics,
                created_at=datetime.now(timezone.utc).isoformat(),
            )

            st.write("Generating question bank...")
            bank = generate_question_bank(module, llm)

            st.write("Saving to database...")
            db_path = os.environ.get("AI_TUTOR_DB_PATH", "data/ai_tutor.db")
            user_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, username))
            save_user(user_id, username, db_path=db_path)
            save_module(module.module_id, module.title, uploaded_file.name, db_path=db_path)

            # Store everything in session state
            st.session_state["module"] = module
            st.session_state["bank"] = bank
            st.session_state["doc"] = doc
            st.session_state["user_id"] = user_id
            st.session_state["username"] = username
            st.session_state["db_path"] = db_path
            st.session_state["page"] = "learn"

            status.update(label="Module ready!", state="complete")

        except Exception as e:
            status.update(label="Failed", state="error")
            st.error(f"Could not process the document: {e}")
            raise
        finally:
            os.unlink(tmp_path)

    st.rerun()
