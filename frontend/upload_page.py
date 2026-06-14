from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone

import streamlit as st

from backend.analytics.db import get_db
from backend.analytics.persistence import save_module, save_user
from backend.core.llm_client import LLMFactory


def render_upload_page() -> None:
    st.title("AI Tutor")
    st.subheader("Transform any PDF into an interactive learning module")

    progress = st.session_state.get("pipeline_progress")
    if progress and progress["state"] not in ("completed",):
        _pipeline_status_fragment()
        return

    username = st.text_input("Your name (used for analytics)", placeholder="e.g. Alice")
    uploaded = st.file_uploader("Upload a PDF document", type=["pdf"])

    missing = []
    if not username:
        missing.append("enter your name")
    if not uploaded:
        missing.append("upload a PDF")
    if missing:
        st.caption(f"To enable: {' and '.join(missing)}")

    if not st.button("Start Learning", disabled=bool(missing), type="primary"):
        return

    if not username.strip():
        st.error("Please enter your name.")
        return

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(uploaded.read())
        tmp_path = tmp.name

    db = get_db()
    user_id = save_user(username.strip(), db=db)
    db.close()

    _start_pipeline(tmp_path, user_id, username.strip())
    st.rerun()


def _start_pipeline(tmp_path: str, user_id: str, username: str) -> None:
    provider = st.session_state.get("llm_provider", "anthropic")
    model = st.session_state.get("llm_model", "claude-sonnet-4-6")

    abort_event = threading.Event()
    module_id = str(uuid.uuid4())

    progress = {
        "state": "parsing",
        "current_topic": "",
        "detail": "",
        "topics": [],
        "enriched_topics": [],
        "total_topics": 0,
        "topics_enriched": 0,
        "ready": False,
        "module_id": module_id,
        "doc_title": "",
        "doc_id": "",
        "started_at": time.monotonic(),
        "error": None,
        "module": None,
        "bank": None,
        "user_id": user_id,
        "username": username,
    }

    st.session_state["pipeline_progress"] = progress
    st.session_state["pipeline_abort_event"] = abort_event

    thread = threading.Thread(
        target=_run_pipeline_bg,
        args=(tmp_path, user_id, username, provider, model, progress, abort_event),
        daemon=True,
        name="pipeline-worker",
    )
    thread.start()


def _run_pipeline_bg(
    tmp_path: str,
    user_id: str,
    username: str,
    provider: str,
    model: str,
    progress: dict,
    abort_event: threading.Event,
) -> None:
    try:
        from backend.content.audio_generator import generate_audio
        from backend.content.content_enricher import enrich
        from backend.content.diagram_generator import generate_diagrams
        from backend.content.inline_question_gen import generate_inline_questions
        from backend.content.models import LearningModule
        from backend.content.topic_decomposer import decompose, _format_sections
        from backend.ingestion.pdf_parser import parse_pdf
        from backend.quiz.question_bank import generate_question_bank

        # Parse PDF
        progress["state"] = "parsing"
        progress["detail"] = "Reading PDF..."
        doc = parse_pdf(tmp_path, max_pages=4)
        progress["doc_title"] = doc.title
        progress["doc_id"] = doc.doc_id
        progress["detail"] = (
            f"Parsed {doc.title} — {len(doc.sections)} section(s), "
            f"{doc.total_pages} page(s)"
        )

        if abort_event.is_set():
            progress["state"] = "aborted"
            return

        # Connect to LLM + decompose
        progress["state"] = "decomposing"
        progress["detail"] = f"Connecting to {provider}..."
        llm = LLMFactory.create(provider=provider, model=model)

        if abort_event.is_set():
            progress["state"] = "aborted"
            return

        progress["detail"] = "Identifying learning topics..."
        cached_blocks = llm.make_cached_document_blocks(_format_sections(doc))
        topics = decompose(doc, llm)
        progress["topics"] = topics
        progress["total_topics"] = len(topics)
        progress["detail"] = f"{len(topics)} topic(s) identified"

        if abort_event.is_set():
            progress["state"] = "aborted"
            return

        # Enrich each topic — publish incrementally
        progress["state"] = "enriching"
        enriched_topics = []
        for i, topic in enumerate(topics, 1):
            if abort_event.is_set():
                progress["state"] = "aborted"
                return

            progress["current_topic"] = topic.title
            progress["detail"] = f"Enriching topic {i}/{len(topics)}: {topic.title}"

            source_text = "\n\n".join(
                s.body
                for s in doc.sections
                if s.section_id in set(topic.source_section_ids)
            )

            enriched = enrich(topic, source_text, llm, cached_blocks=cached_blocks)

            if abort_event.is_set():
                progress["state"] = "aborted"
                return

            enriched.diagrams = generate_diagrams(enriched, llm)

            if abort_event.is_set():
                progress["state"] = "aborted"
                return

            enriched.inline_questions = generate_inline_questions(enriched, llm)

            progress["detail"] = f"Generating audio for {topic.title}..."
            try:
                enriched.audio_path = generate_audio(enriched.content_md, topic.topic_id)
            except Exception:
                enriched.audio_path = ""

            enriched_topics.append(enriched)
            progress["enriched_topics"] = list(enriched_topics)
            progress["topics_enriched"] = i

            if i == 1:
                progress["ready"] = True

        if abort_event.is_set():
            progress["state"] = "aborted"
            return

        module = LearningModule(
            module_id=progress["module_id"],
            title=doc.title,
            source_doc_id=doc.doc_id,
            topics=enriched_topics,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        # Generate quiz bank
        progress["state"] = "quiz"
        progress["detail"] = "Generating quiz questions..."
        progress["current_topic"] = ""
        bank = generate_question_bank(module, llm)
        progress["bank"] = bank
        progress["detail"] = f"{len(bank.questions)} quiz questions generated"

        if abort_event.is_set():
            progress["state"] = "aborted"
            return

        # Save to database
        progress["state"] = "saving"
        progress["detail"] = "Saving module..."
        db = get_db()
        try:
            save_module(
                module_id=module.module_id,
                title=module.title,
                source_filename=doc.source_filename,
                module_json=module.to_json(),
                question_bank_json=json.dumps(_bank_to_dict(bank)),
                created_by=user_id,
                db=db,
            )
        finally:
            db.close()

        progress["module"] = module
        progress["state"] = "completed"
        progress["detail"] = "Module ready!"

    except Exception as exc:
        progress["state"] = "failed"
        progress["error"] = str(exc)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@st.fragment(run_every=2)
def _pipeline_status_fragment() -> None:
    progress = st.session_state.get("pipeline_progress")
    if progress is None:
        return

    state = progress["state"]
    elapsed = int(time.monotonic() - progress["started_at"])

    if state in ("parsing", "decomposing"):
        st.info(f"{progress['detail'] or 'Preparing...'} ({elapsed}s)")

    elif state == "enriching":
        if progress.get("ready"):
            _redirect_to_viewer(progress)
            return

        total = progress["total_topics"]
        done = progress["topics_enriched"]
        if total > 0:
            st.progress(done / total, text=f"Enriching topic {done + 1}/{total}...")
        st.caption(progress.get("detail", ""))
        st.caption(f"Elapsed: {elapsed}s")
        _abort_button()

    elif state in ("quiz", "saving"):
        st.info(f"{progress['detail']} ({elapsed}s)")
        _abort_button()

    elif state == "failed":
        st.error(f"Generation failed: {progress['error']}")
        st.caption(f"Failed after {elapsed}s")
        if st.button("Retry", type="primary"):
            _cleanup_pipeline_state()
            st.rerun()

    elif state == "aborted":
        st.warning(f"Generation was cancelled after {elapsed}s.")
        if st.button("Start New", type="primary"):
            _cleanup_pipeline_state()
            st.rerun()


def _redirect_to_viewer(progress: dict) -> None:
    from backend.content.models import LearningModule

    enriched = progress.get("enriched_topics", [])
    if not enriched:
        return

    module = LearningModule(
        module_id=progress["module_id"],
        title=progress["doc_title"],
        source_doc_id=progress["doc_id"],
        topics=list(enriched),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    st.session_state["module"] = module
    st.session_state["user_id"] = progress["user_id"]
    st.session_state["username"] = progress["username"]
    st.session_state["page"] = "tutor_room"
    st.rerun()


def _abort_button() -> None:
    if st.button("Abort Generation", type="secondary"):
        abort_event = st.session_state.get("pipeline_abort_event")
        if abort_event:
            abort_event.set()


def _cleanup_pipeline_state() -> None:
    for key in ("pipeline_progress", "pipeline_abort_event"):
        st.session_state.pop(key, None)


def _bank_to_dict(bank) -> dict:
    return {"module_id": bank.module_id, "questions": [asdict(q) for q in bank.questions]}
