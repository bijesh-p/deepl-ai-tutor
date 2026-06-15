from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone

import streamlit as st

from backend.core.llm_client import LLMFactory


def render_upload_page() -> None:
    # Guard: must be logged in
    username = st.session_state.get("username", "")
    user_id = st.session_state.get("user_id", "")
    db_path = st.session_state.get("db_path", "")
    if not username or not user_id:
        st.session_state["page"] = "login"
        st.rerun()
        return

    # ── If pipeline is running or just finished, show status / redirect ──────
    progress = st.session_state.get("pipeline_progress")
    if progress:
        state = progress["state"]
        if state == "completed":
            # Pipeline finished in the background — redirect now
            _handle_completed(progress)
            return
        if state not in ("failed", "aborted"):
            _pipeline_status_fragment()
            return
        # failed/aborted fall through to upload form below

    # ── Upload form ───────────────────────────────────────────────────────────
    st.title("New Module")
    st.caption("Upload a PDF to create an interactive learning module.")

    with st.form("upload_form"):
        uploaded = st.file_uploader(
            "PDF document",
            type=["pdf"],
            help="The document will be converted into slides, diagrams, audio, and quizzes.",
        )
        cached_name = st.session_state.get("_cached_upload_name")
        if cached_name:
            st.info(f"Previous file **{cached_name}** will be re-used if no new file is chosen.")
        submitted = st.form_submit_button("Start Learning", type="primary")

    if not submitted:
        return

    if uploaded is None:
        cached = st.session_state.get("_cached_upload_bytes")
        if cached is None:
            st.error("Please upload a PDF.")
            return
        uploaded_bytes = cached
    else:
        uploaded_bytes = uploaded.read()
        st.session_state["_cached_upload_bytes"] = uploaded_bytes
        st.session_state["_cached_upload_name"] = uploaded.name

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(uploaded_bytes)
        tmp_path = tmp.name

    _start_pipeline(tmp_path, user_id, username, db_path)
    st.rerun()


def _start_pipeline(tmp_path: str, user_id: str, username: str, db_path: str) -> None:
    provider = st.session_state.get("llm_provider", "anthropic")
    model = st.session_state.get("llm_model", "claude-sonnet-4-6")
    tracing_enabled = st.session_state.get("tracing_enabled", True)
    audio_enabled = st.session_state.get("audio_enabled", True)

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
        "audio_enabled": audio_enabled,
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
        from backend.core.mcp_client import get_client
        from backend.ingestion.models import Document
        from backend.observability.tracer import get_tracer
        from backend.quiz.question_bank import generate_question_bank
        tracer = get_tracer() if progress.get("tracing_enabled", True) else _noop_tracer()

        # Parse PDF via the document_server MCP tool
        progress["state"] = "parsing"
        progress["detail"] = "Reading PDF..."
        doc_json = get_client("document_server").call(
            "extract_text_from_pdf", file_path=tmp_path, max_pages=4
        )
        doc = Document.from_json(doc_json)
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

        # Generate diagnostic audio immediately — pure TTS, no LLM needed.
        # Plays as soon as the student lands on the diagnostic page (~3s from here).
        if progress.get("audio_enabled", True):
            try:
                from backend.content.audio_generator import generate_diagnostic_audio
                first_title = doc.sections[0].title if doc.sections else doc.title
                progress["diagnostic_audio_path"] = generate_diagnostic_audio(first_title)
            except Exception:
                progress["diagnostic_audio_path"] = ""
        else:
            progress["diagnostic_audio_path"] = ""

        # Prefetch diagnostic questions for slide 1 in background — ready by redirect.
        diag_future = _prefetch_diagnostic(llm, doc, progress)

        # Sliding-window pipeline: reads 500 words at a time, assesses whether
        # enough material exists for a slide, enriches immediately and publishes.
        # Sets progress["ready"]=True after first slide → redirect to tutor room.
        enriched_topics = run_sliding_pipeline(
            doc, llm, progress, abort_event, tracer
        )

        # Collect prefetched diagnostic (may already be done)
        try:
            progress["diagnostic_questions"] = diag_future.result(timeout=30)
        except Exception:
            progress["diagnostic_questions"] = []

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

        # Save to database via the storage_server MCP tool
        progress["state"] = "saving"
        progress["detail"] = "Saving module..."
        get_client("storage_server").call(
            "save_module_to_db",
            module_id=module.module_id,
            title=module.title,
            source_filename=doc.source_filename,
            module_json=module.to_json(),
            question_bank_json=json.dumps(_bank_to_dict(bank)),
            created_by=user_id,
            db_path=db_path,
        )

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
            st.caption(f"Previous file **{cached_name}** will be re-used on retry.")
        if st.button("Retry", type="primary"):
            _cleanup_pipeline_state()
            st.rerun()

    elif state == "aborted":
        st.warning(f"Generation was cancelled after {elapsed}s.")
        if st.button("Upload New File", type="primary"):
            _cleanup_pipeline_state()
            st.session_state.pop("_cached_upload_bytes", None)
            st.session_state.pop("_cached_upload_name", None)
            st.rerun()


def _handle_completed(progress: dict) -> None:
    """Pipeline finished fully — set module/bank in session state and go to tutor room."""
    from backend.content.models import LearningModule

    module = progress.get("module")
    if module is None:
        # Build from enriched topics if full module object not yet set
        enriched = progress.get("enriched_topics", [])
        if not enriched:
            _cleanup_pipeline_state()
            st.rerun()
            return
        module = LearningModule(
            module_id=progress["module_id"],
            title=progress["doc_title"],
            source_doc_id=progress["doc_id"],
            topics=list(enriched),
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    bank = progress.get("bank")
    st.session_state["module"] = module
    if bank:
        st.session_state["bank"] = bank
    st.session_state["page"] = "tutor_room"
    _cleanup_pipeline_state()
    st.rerun()


def _redirect_to_viewer(progress: dict) -> None:
    """Early redirect — first slide ready, background continues enriching."""
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
    st.session_state["page"] = "tutor_room"
    st.rerun()


def _prefetch_diagnostic(llm, doc, progress: dict) -> Future:
    """Prefetch diagnostic questions for the first topic in a background thread.

    Runs in parallel with slide 1 enrichment so questions are ready at redirect.
    """
    from concurrent.futures import ThreadPoolExecutor
    from backend.interactive_tutor.graph import _DIAGNOSTIC_SCHEMA, _DIAGNOSTIC_SYSTEM

    first_section = doc.sections[0] if doc.sections else None
    title = first_section.title if first_section else doc.title
    summary = (first_section.body[:300] if first_section else "")

    def _fetch():
        try:
            result = llm.generate(
                prompt=(
                    f"Topic: {title}\nSummary: {summary}\n\n"
                    "Generate diagnostic questions to assess the student's prior knowledge."
                ),
                system=_DIAGNOSTIC_SYSTEM,
                tool_schema=_DIAGNOSTIC_SCHEMA,
            )
            return result.get("questions", []) if isinstance(result, dict) else []
        except Exception:
            return []

    ex = ThreadPoolExecutor(max_workers=1, thread_name_prefix="diag-prefetch")
    return ex.submit(_fetch)


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
