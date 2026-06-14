from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone

import streamlit as st

from backend.analytics.db import get_db
from backend.analytics.persistence import load_user_profile, save_module, save_user
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
    profile = load_user_profile(user_id, db=db)
    db.close()

    st.session_state["user_profile"] = profile
    _start_pipeline(tmp_path, user_id, username.strip())
    st.rerun()


def _start_pipeline(tmp_path: str, user_id: str, username: str) -> None:
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
        "tracing_enabled": tracing_enabled,
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
        from backend.content.models import LearningModule
        from backend.content.topic_decomposer import decompose, _format_sections
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

        # Enrich topics in parallel — up to 4 at once, publish as each completes
        progress["state"] = "enriching"
        enriched_topics: list = [None] * len(topics)

        with ThreadPoolExecutor(max_workers=min(4, len(topics))) as ex:
            future_to_idx = {
                ex.submit(
                    _enrich_topic,
                    topic, i, doc, llm, cached_blocks, tracer, abort_event,
                ): i
                for i, topic in enumerate(topics)
            }
            for future in as_completed(future_to_idx):
                if abort_event.is_set():
                    break
                idx = future_to_idx[future]
                result = future.result()
                if result is not None:
                    enriched_topics[idx] = result
                    completed = [e for e in enriched_topics if e is not None]
                    progress["enriched_topics"] = completed
                    progress["topics_enriched"] = len(completed)
                    progress["current_topic"] = result.topic.title
                    progress["detail"] = (
                        f"Enriched {len(completed)}/{len(topics)}: {result.topic.title}"
                    )
                    if idx == 0:
                        progress["ready"] = True

        if abort_event.is_set():
            progress["state"] = "aborted"
            return

        # Drop any slots that failed (None) — preserve order of successes
        enriched_topics = [e for e in enriched_topics if e is not None]

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


def _enrich_topic(topic, idx, doc, llm, cached_blocks, tracer, abort_event):
    """Enrich a single topic with diagrams, questions, and audio. Thread-safe."""
    from backend.content.audio_generator import generate_audio
    from backend.content.content_enricher import enrich
    from backend.content.diagram_generator import generate_diagrams
    from backend.content.inline_question_gen import generate_inline_questions

    if abort_event.is_set():
        return None

    source_text = "\n\n".join(
        s.body for s in doc.sections if s.section_id in set(topic.source_section_ids)
    )

    with tracer.start_as_current_span(
        "pipeline.enrich_topic",
        attributes={"topic.title": topic.title, "topic.index": idx},
    ):
        enriched = enrich(topic, source_text, llm, cached_blocks=cached_blocks)

    if abort_event.is_set():
        return None

    # Diagram and inline questions are independent — run in parallel
    with ThreadPoolExecutor(max_workers=2) as inner:
        fut_diag = inner.submit(generate_diagrams, enriched, llm)
        fut_qs = inner.submit(generate_inline_questions, enriched, llm)
        try:
            enriched.diagrams = fut_diag.result()
        except Exception:
            enriched.diagrams = []
        try:
            enriched.inline_questions = fut_qs.result()
        except Exception:
            enriched.inline_questions = []

    if abort_event.is_set():
        return None

    try:
        diagram = enriched.diagrams[0] if enriched.diagrams else None
        with tracer.start_as_current_span(
            "pipeline.generate_audio",
            attributes={"topic.title": topic.title},
        ):
            enriched.audio_path = generate_audio(
                enriched.content_md,
                topic.topic_id,
                diagram_caption=diagram.caption if diagram else "",
                diagram_mermaid=diagram.content if diagram else "",
            )
    except Exception:
        enriched.audio_path = ""

    return enriched


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


class _NoopSpan:
    """Context manager that does nothing — used when tracing is disabled."""
    def __enter__(self): return self
    def __exit__(self, *_): pass


class _NoopTracer:
    def start_as_current_span(self, name: str, **kwargs) -> _NoopSpan:
        return _NoopSpan()


def _noop_tracer() -> _NoopTracer:
    return _NoopTracer()
