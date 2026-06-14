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

from backend.analytics.db import db_path_for_user, get_db
from backend.analytics.persistence import load_user_profile, save_module, save_user
from backend.core.llm_client import LLMFactory


def render_upload_page() -> None:
    st.title("AI Tutor")
    st.subheader("Transform any PDF into an interactive learning module")

    progress = st.session_state.get("pipeline_progress")
    if progress and progress["state"] not in ("completed",):
        _pipeline_status_fragment()
        return

    # ── Login form ────────────────────────────────────────────────────────────
    with st.form("login_form"):
        st.markdown("#### Sign in")
        username = st.text_input(
            "Username",
            value=st.session_state.get("_last_username", ""),
            placeholder="e.g. alice",
        )
        st.text_input(
            "Password",
            type="password",
            placeholder="(authentication not required)",
            disabled=True,
        )
        uploaded = st.file_uploader(
            "Upload a PDF",
            type=["pdf"],
            help="The document will be converted into an interactive learning module.",
        )
        submitted = st.form_submit_button("Start Learning", type="primary")

    if not submitted:
        return

    # ── Validation ────────────────────────────────────────────────────────────
    errors = []
    if not username.strip():
        errors.append("Please enter a username.")
    if uploaded is None:
        # Fallback to previously uploaded file stored in session state
        cached = st.session_state.get("_cached_upload_bytes")
        cached_name = st.session_state.get("_cached_upload_name", "document.pdf")
        if cached is None:
            errors.append("Please upload a PDF.")
        else:
            uploaded_bytes = cached
            uploaded_name = cached_name
    else:
        uploaded_bytes = uploaded.read()
        uploaded_name = uploaded.name
        # Cache so retry works without re-selecting the file
        st.session_state["_cached_upload_bytes"] = uploaded_bytes
        st.session_state["_cached_upload_name"] = uploaded_name

    if errors:
        for e in errors:
            st.error(e)
        return

    # Remember username for next render
    st.session_state["_last_username"] = username.strip()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(uploaded_bytes)
        tmp_path = tmp.name

    db_path = db_path_for_user(username.strip())
    db = get_db(db_path)
    user_id = save_user(username.strip(), db=db)
    profile = load_user_profile(user_id, db=db)
    db.close()

    st.session_state["user_profile"] = profile
    st.session_state["db_path"] = db_path
    _start_pipeline(tmp_path, user_id, username.strip(), db_path)
    st.rerun()


def _start_pipeline(tmp_path: str, user_id: str, username: str, db_path: str) -> None:
    provider = st.session_state.get("llm_provider", "anthropic")
    model = st.session_state.get("llm_model", "claude-sonnet-4-6")
    tracing_enabled = st.session_state.get("tracing_enabled", True)

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
        "db_path": db_path,
        "tracing_enabled": tracing_enabled,
    }

    st.session_state["pipeline_progress"] = progress
    st.session_state["pipeline_abort_event"] = abort_event

    thread = threading.Thread(
        target=_run_pipeline_bg,
        args=(tmp_path, user_id, username, provider, model, db_path, progress, abort_event),
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
    db_path: str,
    progress: dict,
    abort_event: threading.Event,
) -> None:
    try:
        from backend.content.models import LearningModule
        from backend.content.sliding_pipeline import run_sliding_pipeline
        from backend.ingestion.pdf_parser import parse_pdf
        from backend.observability.tracer import get_tracer
        from backend.quiz.question_bank import generate_question_bank
        tracer = get_tracer() if progress.get("tracing_enabled", True) else _noop_tracer()

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

        progress["state"] = "enriching"
        progress["detail"] = "Connecting to LLM..."
        llm = LLMFactory.create(provider=provider, model=model)

        if abort_event.is_set():
            progress["state"] = "aborted"
            return

        # Sliding-window pipeline: reads 500 words at a time, assesses whether
        # enough material exists for a slide, enriches immediately and publishes.
        # Sets progress["ready"]=True after first slide → redirect to tutor room.
        enriched_topics = run_sliding_pipeline(
            doc, llm, progress, abort_event, tracer
        )

        if abort_event.is_set():
            progress["state"] = "aborted"
            return

        if not enriched_topics:
            progress["state"] = "failed"
            progress["error"] = "No presentable concepts found in document."
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
        db = get_db(db_path)
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

    if state in ("parsing",):
        st.info(f"{progress['detail'] or 'Preparing...'} ({elapsed}s)")

    elif state == "enriching":
        if progress.get("ready"):
            _redirect_to_viewer(progress)
            return

        done = progress.get("topics_enriched", 0)
        detail = progress.get("detail", "Reading document...")
        st.info(f"{detail} ({elapsed}s)")
        if done > 0:
            st.metric("Slides ready", done)
        _abort_button()

    elif state in ("quiz", "saving"):
        st.info(f"{progress['detail']} ({elapsed}s)")
        _abort_button()

    elif state == "failed":
        st.error(f"Generation failed: {progress['error']}")
        st.caption(f"Failed after {elapsed}s")
        cached_name = st.session_state.get("_cached_upload_name")
        if cached_name:
            st.info(f"Previous file **{cached_name}** will be re-used on retry.")
        if st.button("Retry", type="primary"):
            _cleanup_pipeline_state()
            st.rerun()

    elif state == "aborted":
        st.warning(f"Generation was cancelled after {elapsed}s.")
        if st.button("Start New", type="primary"):
            _cleanup_pipeline_state()
            # Clear cached file so the user picks a fresh one
            st.session_state.pop("_cached_upload_bytes", None)
            st.session_state.pop("_cached_upload_name", None)
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


class _NoopSpan:
    """Context manager that does nothing — used when tracing is disabled."""
    def __enter__(self): return self
    def __exit__(self, *_): pass


class _NoopTracer:
    def start_as_current_span(self, name: str, **kwargs) -> _NoopSpan:
        return _NoopSpan()


def _noop_tracer() -> _NoopTracer:
    return _NoopTracer()
