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
    if progress and progress["state"] in ("running", "completed", "failed", "aborted"):
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

    if not st.button("Generate Learning Module", disabled=bool(missing)):
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
    progress = {
        "state": "running",
        "step": 1,
        "step_label": "Parsing PDF...",
        "substep": "",
        "detail": "",
        "total_topics": 0,
        "topics_enriched": 0,
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
        from backend.content.content_enricher import enrich
        from backend.content.diagram_generator import generate_diagrams
        from backend.content.inline_question_gen import generate_inline_questions
        from backend.content.models import LearningModule
        from backend.content.topic_decomposer import decompose, _format_sections
        from backend.ingestion.pdf_parser import parse_pdf
        from backend.quiz.question_bank import generate_question_bank

        # Step 1: Parse PDF
        progress["step"] = 1
        progress["step_label"] = "Parsing PDF..."
        doc = parse_pdf(tmp_path, max_pages=4)
        progress["detail"] = (
            f"Parsed {doc.title} — {len(doc.sections)} section(s), "
            f"{doc.total_pages} page(s)"
        )

        if abort_event.is_set():
            progress["state"] = "aborted"
            return

        # Step 2: Connect to LLM
        progress["step"] = 2
        progress["step_label"] = "Connecting to LLM..."
        progress["substep"] = f"{provider} / {model}"
        llm = LLMFactory.create(provider=provider, model=model)
        progress["detail"] = f"Connected — model: {llm.model}"

        if abort_event.is_set():
            progress["state"] = "aborted"
            return

        # Step 3: Decompose
        progress["step"] = 3
        progress["step_label"] = "Decomposing into topics..."
        cached_blocks = llm.make_cached_document_blocks(_format_sections(doc))
        topics = decompose(doc, llm)
        progress["total_topics"] = len(topics)
        topic_names = ", ".join(t.title for t in topics)
        progress["detail"] = f"{len(topics)} topic(s): {topic_names}"

        if abort_event.is_set():
            progress["state"] = "aborted"
            return

        # Step 4: Enrich each topic
        progress["step"] = 4
        progress["step_label"] = "Enriching topics..."
        enriched_topics = []
        for i, topic in enumerate(topics, 1):
            if abort_event.is_set():
                progress["state"] = "aborted"
                return

            progress["substep"] = f"Topic {i}/{len(topics)}: {topic.title}"

            source_text = "\n\n".join(
                s.body
                for s in doc.sections
                if s.section_id in set(topic.source_section_ids)
            )

            progress["detail"] = "Enriching content..."
            enriched = enrich(topic, source_text, llm, cached_blocks=cached_blocks)

            if abort_event.is_set():
                progress["state"] = "aborted"
                return

            progress["detail"] = "Generating diagrams..."
            enriched.diagrams = generate_diagrams(enriched, llm)

            if abort_event.is_set():
                progress["state"] = "aborted"
                return

            progress["detail"] = "Generating questions..."
            enriched.inline_questions = generate_inline_questions(enriched, llm)

            enriched_topics.append(enriched)
            progress["topics_enriched"] = i

        if abort_event.is_set():
            progress["state"] = "aborted"
            return

        module = LearningModule(
            module_id=str(uuid.uuid4()),
            title=doc.title,
            source_doc_id=doc.doc_id,
            topics=enriched_topics,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        # Step 5: Quiz bank
        progress["step"] = 5
        progress["step_label"] = "Generating quiz..."
        progress["substep"] = ""
        bank = generate_question_bank(module, llm)
        progress["detail"] = f"{len(bank.questions)} questions generated"

        if abort_event.is_set():
            progress["state"] = "aborted"
            return

        # Step 6: Save
        progress["step"] = 6
        progress["step_label"] = "Saving to database..."
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
        progress["bank"] = bank
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

    if state == "running":
        step = progress["step"]
        total_topics = progress["total_topics"]
        topics_done = progress["topics_enriched"]

        if step == 4 and total_topics > 0:
            fraction = (3 + topics_done / total_topics) / 6
        else:
            fraction = max(0.0, (step - 1) / 6)
        fraction = min(fraction, 1.0)

        st.progress(fraction, text=f"Step {step}/6: {progress['step_label']}")
        if progress["substep"]:
            st.caption(progress["substep"])
        if progress["detail"]:
            st.caption(progress["detail"])
        st.caption(f"Elapsed: {elapsed}s")

        if st.button("Abort Generation", type="secondary"):
            abort_event = st.session_state.get("pipeline_abort_event")
            if abort_event:
                abort_event.set()

    elif state == "completed":
        st.success(f"Module ready! ({elapsed}s)")
        st.session_state["module"] = progress["module"]
        st.session_state["bank"] = progress["bank"]
        st.session_state["user_id"] = progress["user_id"]
        st.session_state["username"] = progress["username"]
        _cleanup_pipeline_state()
        st.session_state["page"] = "learn"
        st.rerun()

    elif state == "failed":
        st.error(f"Generation failed: {progress['error']}")
        st.caption(f"Failed after {elapsed}s at step {progress['step']}/6")
        if st.button("Retry", type="primary"):
            _cleanup_pipeline_state()
            st.rerun()

    elif state == "aborted":
        st.warning(f"Generation was cancelled after {elapsed}s.")
        if st.button("Start New Generation", type="primary"):
            _cleanup_pipeline_state()
            st.rerun()


def _cleanup_pipeline_state() -> None:
    for key in ("pipeline_progress", "pipeline_abort_event"):
        st.session_state.pop(key, None)


def _bank_to_dict(bank) -> dict:
    return {"module_id": bank.module_id, "questions": [asdict(q) for q in bank.questions]}
