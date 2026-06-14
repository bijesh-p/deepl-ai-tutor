from __future__ import annotations
import os
import uuid
from datetime import datetime, timezone

import streamlit as st

_MAX_MB = int(os.environ.get("AI_TUTOR_MAX_FILE_MB", "50"))
_UPLOAD_DIR = os.environ.get("AI_TUTOR_UPLOAD_DIR", "data/uploads")


def render_upload_page() -> None:
    st.title("📚 AI Tutor")
    st.subheader("Transform your documents into interactive learning modules")

    username = st.text_input("Your name (used for analytics):", key="username_input")
    uploaded_file = st.file_uploader(
        "Upload a document", type=["pdf", "pptx", "docx"]
    )

    if uploaded_file:
        size_mb = len(uploaded_file.getvalue()) / (1024 * 1024)
        if size_mb > _MAX_MB:
            st.error(f"File exceeds {_MAX_MB} MB limit ({size_mb:.1f} MB).")
            return

    if st.button(
        "Generate Module",
        type="primary",
        disabled=not (uploaded_file and username.strip()),
    ):
        _run_pipeline(uploaded_file, username.strip())


def _run_pipeline(uploaded_file, username: str) -> None:
    ext = uploaded_file.name.rsplit(".", 1)[-1].lower()

    # --- Step 1: Save file ---
    with st.spinner("Saving file…"):
        os.makedirs(_UPLOAD_DIR, exist_ok=True)
        file_path = os.path.join(_UPLOAD_DIR, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getvalue())

    # --- Step 2: Parse document ---
    with st.spinner("Parsing document…"):
        try:
            doc = _parse(ext, file_path)
        except Exception as exc:
            st.error(f"Could not parse this file: {exc}")
            return

    # --- Step 3: Create / resolve user ---
    user_id = str(uuid.uuid4())
    from analytics.db import get_db
    from analytics.persistence import save_user
    conn = get_db()
    user_id = save_user(user_id, username, conn)
    conn.close()
    st.session_state.user_id = user_id
    st.session_state.username = username

    # --- Step 4: Content generation ---
    progress = st.progress(0, text="Generating learning module… (1–3 min)")
    try:
        from content.llm_client import make_llm_client
        from content.topic_decomposer import decompose
        from content.content_enricher import enrich
        from content.diagram_generator import generate_diagrams
        from content.inline_question_gen import generate_inline_questions
        from content.models import Diagram, LearningModule

        llm = make_llm_client()
        topics = decompose(doc, llm)
        section_map = {s.section_id: s for s in doc.sections}
        enriched_topics = []

        for i, topic in enumerate(topics):
            raw_content = "\n\n".join(
                f"## {section_map[sid].title}\n\n{section_map[sid].body}"
                for sid in topic.source_section_ids
                if sid in section_map
            )
            et = enrich(topic, llm, raw_content=raw_content)
            et.diagrams = generate_diagrams(et, llm)

            # Attach extracted images from source sections
            for sid in topic.source_section_ids:
                if sid in section_map:
                    for img in section_map[sid].images:
                        et.diagrams.append(
                            Diagram(
                                diagram_id=img.image_id,
                                diagram_type="extracted_image",
                                content=img.file_path,
                                caption=img.caption or "",
                            )
                        )

            et.inline_questions = generate_inline_questions(et, llm)
            enriched_topics.append(et)
            progress.progress(
                int((i + 1) / len(topics) * 70),
                text=f"Enriched topic {i+1}/{len(topics)}…",
            )

        module = LearningModule(
            module_id=str(uuid.uuid4()),
            title=doc.title,
            source_doc_id=doc.doc_id,
            topics=enriched_topics,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as exc:
        st.error(f"Content generation failed: {exc}")
        if st.button("Retry"):
            st.rerun()
        return

    # --- Step 5: Quiz generation ---
    progress.progress(75, text="Generating quiz questions…")
    try:
        from quiz.question_bank import generate_question_bank
        bank = generate_question_bank(module, llm)
    except Exception as exc:
        st.error(f"Quiz generation failed: {exc}")
        return

    # --- Step 6: Persist module ---
    progress.progress(95, text="Saving…")
    from analytics.db import get_db
    from analytics.persistence import save_module
    conn = get_db()
    save_module(module, doc.source_filename, conn)
    conn.close()

    progress.progress(100, text="Done!")
    st.session_state.module = module
    st.session_state.question_bank = bank
    st.session_state.page = "learn"
    st.rerun()


def _parse(ext: str, file_path: str):
    if ext == "pdf":
        from ingestion.pdf_parser import parse_pdf
        return parse_pdf(file_path)
    if ext == "pptx":
        from ingestion.pptx_parser import parse_pptx
        return parse_pptx(file_path)
    if ext == "docx":
        from ingestion.docx_parser import parse_docx
        return parse_docx(file_path)
    raise ValueError(f"Unsupported format: .{ext}")
