from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from backend.core.llm_client import LLMFactory
from frontend.nav import render_back_button
from frontend.styles import (
    step_progress_html,
    page_header_html,
    parsing_status_html,
    slide_chips_html,
    skeleton_slide_html,
    quiz_generating_html,
    saving_status_html,
    bouncing_dots_html,
)

_TOOL_FOR_EXT: dict[str, str] = {
    ".pdf": "extract_text_from_pdf",
    ".pptx": "extract_text_from_pptx",
    ".docx": "extract_text_from_docx",
    ".vtt": "extract_text_from_vtt",
}


def render_upload_page() -> None:
    # Guard: must be logged in
    username = st.session_state.get("username", "")
    user_id = st.session_state.get("user_id", "")
    db_path = st.session_state.get("db_path", "")
    if not username or not user_id:
        st.session_state["page"] = "login"
        st.rerun()
        return

    render_back_button("← Back to Module Library", "module_library", key="_back_upload")

    # ── If pipeline is running or just finished, show status / redirect ──────
    progress = st.session_state.get("pipeline_progress")
    if progress:
        state = progress["state"]
        if state == "completed":
            _render_completed_state(progress)
            return
        if state == "aborted":
            elapsed = int(time.monotonic() - progress.get("started_at", time.monotonic()))
            done = progress.get("topics_enriched", 0)
            st.warning(
                f"Generation cancelled after {elapsed}s."
                + (f" {done} slide(s) had been generated." if done else "")
            )
            _cleanup_pipeline_state()
            # fall through to show upload form
        elif state not in ("failed",):
            _pipeline_status_fragment()
            return
        # failed falls through to upload form below

    # ── Upload form ───────────────────────────────────────────────────────────
    st.markdown(
        page_header_html(
            "New Learning Module",
            "Upload a document and AI Tutor will generate slides, diagrams, audio, and a quiz for you.",
            "📄",
            dark=st.session_state.get("dark_mode", True),
        ),
        unsafe_allow_html=True,
    )

    _default_max_topics = int(os.environ.get("AI_TUTOR_DEFAULT_MAX_TOPICS", "0"))

    with st.form("upload_form"):
        uploaded = st.file_uploader(
            "Choose a document",
            type=["pdf", "pptx", "docx", "vtt"],
            help="PDF, PowerPoint (.pptx), Word (.docx), or VTT transcript (.vtt) — up to 10 pages processed.",
            label_visibility="collapsed",
        )
        cached_name = st.session_state.get("_cached_upload_name")
        if cached_name:
            st.info(f"Re-using **{cached_name}** — upload a new file to replace it.")
        max_topics = st.slider(
            "Slide count (0 = all)",
            min_value=0,
            max_value=20,
            value=_default_max_topics,
            step=1,
            help="Maximum number of slides to generate. Set to 0 to generate all slides from the document.",
        )
        col_btn, col_hint = st.columns([1, 3])
        with col_btn:
            submitted = st.form_submit_button("Generate Module →", type="primary", use_container_width=True)
        with col_hint:
            st.markdown(
                "<div style='padding-top:8px;font-size:12px;color:#9CA3AF;'>"
                "Processing takes 1–3 minutes depending on document length.</div>",
                unsafe_allow_html=True,
            )

    if not submitted:
        return

    if uploaded is None:
        cached = st.session_state.get("_cached_upload_bytes")
        if cached is None:
            st.error("Please upload a PDF, PPTX, DOCX, or VTT file.")
            return
        uploaded_bytes = cached
        original_filename = st.session_state.get("_cached_upload_name", "document.pdf")
        file_ext = Path(original_filename).suffix.lower()
    else:
        uploaded_bytes = uploaded.read()
        original_filename = uploaded.name
        file_ext = Path(original_filename).suffix.lower()
        st.session_state["_cached_upload_bytes"] = uploaded_bytes
        st.session_state["_cached_upload_name"] = original_filename

    if file_ext not in _TOOL_FOR_EXT:
        st.error(f"Unsupported file type: {file_ext!r}. Please upload a PDF, PPTX, DOCX, or VTT.")
        return

    with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as tmp:
        tmp.write(uploaded_bytes)
        tmp_path = tmp.name

    original_filename = st.session_state.get("_cached_upload_name", "")
    _start_pipeline(tmp_path, file_ext, user_id, username, db_path, int(max_topics), original_filename)
    st.rerun()


def _start_pipeline(
    tmp_path: str, file_ext: str, user_id: str, username: str, db_path: str,
    max_topics: int = 0, original_filename: str = "",
) -> None:
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
        "failed_step": None,
        "error_detail": "",
        "module": None,
        "bank": None,
        "user_id": user_id,
        "username": username,
        "db_path": db_path,
        "tracing_enabled": tracing_enabled,
        "audio_enabled": audio_enabled,
        "max_topics": max_topics,
        "original_filename": original_filename,
        "log": [],
    }

    st.session_state["pipeline_progress"] = progress
    st.session_state["pipeline_abort_event"] = abort_event

    thread = threading.Thread(
        target=_run_pipeline_bg,
        args=(
            tmp_path, file_ext, user_id, username, provider, model, db_path,
            progress, abort_event, max_topics, original_filename,
        ),
        daemon=True,
        name="pipeline-worker",
    )
    thread.start()


def _fail(progress: dict, step: str, exc: BaseException | None, user_msg: str) -> None:
    progress["state"] = "failed"
    progress["failed_step"] = step
    progress["error"] = user_msg
    progress["error_detail"] = str(exc) if exc is not None else ""


def _run_pipeline_bg(
    tmp_path: str,
    file_ext: str,
    user_id: str,
    username: str,
    provider: str,
    model: str,
    db_path: str,
    progress: dict,
    abort_event: threading.Event,
    max_topics: int = 0,
    original_filename: str = "",
) -> None:
    def _log(msg: str) -> None:
        elapsed = int(time.monotonic() - progress["started_at"])
        progress["log"].append(f"[{elapsed:>3}s] {msg}")

    try:
        from backend.content.models import LearningModule
        from backend.content.sliding_pipeline import run_sliding_pipeline
        from backend.ingestion.models import Document
        from backend.ingestion.pdf_parser import parse_pdf
        from backend.quiz.question_bank import generate_question_bank
        tracer = _noop_tracer()

        _log(f"max_topics={max_topics}")

        # ── Step 1: Parse (direct — no MCP needed) ───────────────────────────
        progress["state"] = "parsing"
        progress["detail"] = "Reading document..."
        _log("Reading document...")
        try:
            if file_ext == ".pdf":
                doc = parse_pdf(tmp_path, max_pages=25)
            elif file_ext == ".pptx":
                from backend.ingestion.pptx_parser import parse_pptx
                doc = parse_pptx(tmp_path)
            elif file_ext == ".docx":
                from backend.ingestion.docx_parser import parse_docx
                doc = parse_docx(tmp_path)
            elif file_ext == ".vtt":
                from backend.ingestion.vtt_parser import parse_vtt
                doc = parse_vtt(tmp_path)
            else:
                raise ValueError(f"Unsupported format: {file_ext}")
            if original_filename:
                doc.source_filename = original_filename
                if doc.title == Path(tmp_path).stem:
                    doc.title = Path(original_filename).stem
            progress["doc_title"] = doc.title
            progress["doc_id"] = doc.doc_id
            _log(f"Parsed '{doc.title}' — {len(doc.sections)} section(s), {doc.total_pages} page(s)")
        except Exception as exc:
            _fail(progress, "parse", exc,
                  "Could not read the document. The file may be corrupted, "
                  "password-protected, or in an unsupported format.")
            return

        if abort_event.is_set():
            progress["state"] = "aborted"
            return

        # ── Step 2: Connect to LLM ────────────────────────────────────────────
        progress["state"] = "enriching"
        progress["detail"] = "Connecting to LLM..."
        try:
            llm = LLMFactory.create(provider=provider, model=model)
        except Exception as exc:
            _fail(progress, "enrich", exc,
                  "Could not connect to the LLM. Check your API key and provider settings.")
            return

        if abort_event.is_set():
            progress["state"] = "aborted"
            return

        # Generate diagnostic audio immediately — pure TTS, no LLM needed.
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

        # ── Step 3: Enrich (sliding-window pipeline) ──────────────────────────
        try:
            enriched_topics = run_sliding_pipeline(
                doc, llm, progress, abort_event, tracer,
                max_topics=max_topics,
            )
        except ValueError as exc:
            # Raised when the document has no extractable text (e.g. scanned image PDF)
            _fail(progress, "enrich", exc, str(exc))
            return
        except Exception as exc:
            partial = progress.get("enriched_topics", [])
            detail = (
                f" {len(partial)} topic(s) were successfully generated before the failure."
                if partial else ""
            )
            _fail(progress, "enrich", exc, f"Content generation failed.{detail}")
            return

        # Collect prefetched diagnostic (may already be done)
        try:
            progress["diagnostic_questions"] = diag_future.result(timeout=30)
        except Exception:
            progress["diagnostic_questions"] = []

        if abort_event.is_set():
            progress["state"] = "aborted"
            return

        if not enriched_topics:
            _fail(progress, "enrich", None,
                  "No slides could be generated. The document may have very little text content.")
            return

        module = LearningModule(
            module_id=progress["module_id"],
            title=doc.title,
            source_doc_id=doc.doc_id,
            topics=enriched_topics,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        # Publish module early so partial-recovery UI can use it if quiz/save fails
        progress["module"] = module

        # ── Step 4: Quiz ──────────────────────────────────────────────────────
        progress["state"] = "quiz"
        progress["detail"] = "Generating quiz questions..."
        _log("Generating quiz questions...")
        progress["current_topic"] = ""
        try:
            bank = generate_question_bank(module, llm)
            progress["bank"] = bank
            progress["detail"] = f"{len(bank.questions)} quiz questions generated"
        except Exception as exc:
            _fail(progress, "quiz", exc,
                  "Quiz generation failed. The course content is ready — "
                  "you can start learning without a quiz.")
            return

        if abort_event.is_set():
            progress["state"] = "aborted"
            return

        # ── Step 5: Save (direct — no MCP needed) ────────────────────────────
        progress["state"] = "saving"
        progress["detail"] = "Saving module..."
        _log("Saving module to database...")
        try:
            from backend.analytics.db import get_db
            from backend.analytics.persistence import save_module
            conn = get_db(db_path)
            try:
                save_module(
                    module_id=module.module_id,
                    title=module.title,
                    source_filename=original_filename,
                    module_json=module.to_json(),
                    question_bank_json=json.dumps(_bank_to_dict(bank)),
                    created_by=user_id,
                    db=conn,
                )
            finally:
                conn.close()
        except Exception as exc:
            _fail(progress, "save", exc,
                  "Could not save the module to the database. "
                  "The content was generated — you can start learning now, "
                  "but it won't appear in your Module Library.")
            return

        progress["state"] = "completed"
        _log("Module saved. Done!")
        progress["detail"] = "Module ready!"

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


_PIPELINE_STEPS = ["Upload", "Parse", "Generate Slides", "Quiz", "Save"]
_STATE_TO_STEP = {"parsing": 1, "enriching": 2, "quiz": 3, "saving": 4}


@st.fragment(run_every=1)
def _pipeline_status_fragment() -> None:
    progress = st.session_state.get("pipeline_progress")
    if progress is None:
        return

    state = progress["state"]
    elapsed = int(time.monotonic() - progress["started_at"])

    if state == "failed":
        _render_failed_state(progress, elapsed)
        return

    if state == "aborted":
        st.rerun()
        return

    # ── Step progress bar (always shown) ─────────────────────────────────────
    step_idx = _STATE_TO_STEP.get(state, 1)
    st.markdown(step_progress_html(_PIPELINE_STEPS, step_idx, dark=st.session_state.get("dark_mode", True)), unsafe_allow_html=True)

    # ── Per-state animated status cards ──────────────────────────────────────
    dark = st.session_state.get("dark_mode", True)

    if state == "parsing":
        detail = progress.get("detail") or "Reading document…"
        st.markdown(parsing_status_html(detail, elapsed, dark=dark), unsafe_allow_html=True)

    elif state == "enriching":
        done = progress.get("topics_enriched", 0)
        total = progress.get("total_topics", 0)
        enriched = progress.get("enriched_topics", [])
        current = progress.get("current_topic", "")
        detail = progress.get("detail", "")
        avg_secs = progress.get("avg_seconds_per_topic", 0)
        # "active" = slide currently being generated (done + 1 if something is in flight)
        active = done + 1 if (current or done == 0) and (total == 0 or done < total) else done

        # Status line
        if done == 0:
            status_line = detail or "Generating first slide…"
        elif avg_secs > 0 and total > 0:
            remaining = total - done
            eta = int(remaining * avg_secs)
            eta_str = f"~{eta // 60}m {eta % 60}s" if eta > 60 else f"~{eta}s"
            status_line = f"{done} of {total} slides ready · {eta_str} remaining"
        else:
            status_line = detail or f"{done} slide(s) ready"

        st.markdown(_enriching_card_html(
            done=done, total=total, active=active, enriched=enriched,
            current=current, status=status_line, elapsed=elapsed, dark=dark,
        ), unsafe_allow_html=True)

        # Progress bar
        if total > 0:
            st.progress(min(active / total, 1.0), text=f"Generating slide {active} of {total}")
        else:
            st.progress(0.0, text="Assessing document structure…")

        _abort_button()

    elif state == "quiz":
        st.markdown(quiz_generating_html(elapsed, dark=dark), unsafe_allow_html=True)
        _abort_button()

    elif state == "saving":
        st.markdown(saving_status_html(elapsed, dark=dark), unsafe_allow_html=True)

    elif state == "completed":
        st.rerun()


def _enriching_card_html(
    done: int, total: int, active: int, enriched: list, current: str,
    status: str, elapsed: int, dark: bool = False,
) -> str:
    """Single cohesive card for the slide-generation stage."""
    if dark:
        card_bg, card_border = "#0C1929", "#1E3A5F"
        title_color, sub_color = "#93C5FD", "#60A5FA"
        chip_done_bg, chip_done_border, chip_done_text = "#064E3B", "#059669", "#6EE7B7"
        chip_cur_bg, chip_cur_border, chip_cur_text = "#0F1F3D", "#3B82F6", "#93C5FD"
    else:
        card_bg, card_border = "#EFF6FF", "#BFDBFE"
        title_color, sub_color = "#1E3A8A", "#2563EB"
        chip_done_bg, chip_done_border, chip_done_text = "#D1FAE5", "#6EE7B7", "#065F46"
        chip_cur_bg, chip_cur_border, chip_cur_text = "#DBEAFE", "#93C5FD", "#1E40AF"

    elapsed_str = f"{elapsed}s" if elapsed > 0 else "starting…"

    chips = ""
    for et in enriched:
        t = getattr(getattr(et, "topic", None), "title", str(et))
        short = (t[:20] + "…") if len(t) > 20 else t
        chips += (
            f'<span style="display:inline-flex;align-items:center;gap:4px;'
            f'padding:3px 8px;background:{chip_done_bg};border:1px solid {chip_done_border};'
            f'border-radius:999px;font-size:10px;color:{chip_done_text};font-weight:500;">'
            f'✓ {short}</span> '
        )
    if current:
        short = (current[:20] + "…") if len(current) > 20 else current
        chips += (
            f'<span style="display:inline-flex;align-items:center;gap:4px;'
            f'padding:3px 8px;background:{chip_cur_bg};border:1px solid {chip_cur_border};'
            f'border-radius:999px;font-size:10px;color:{chip_cur_text};font-weight:600;'
            f'animation:ai-pulse 1.4s ease-in-out infinite;">'
            f'● {short}…</span>'
        )

    chips_row = f'<div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:8px;">{chips}</div>' if chips else ""

    progress_text = f"slide {active} of {total}" if total > 0 else "analyzing…"

    return (
        f'<div style="padding:18px 20px;background:{card_bg};border:1px solid {card_border};'
        f'border-radius:12px;display:flex;align-items:flex-start;gap:16px;">'

        f'<div style="flex-shrink:0;width:42px;height:42px;border-radius:50%;'
        f'background:#2563EB;display:flex;align-items:center;justify-content:center;">'
        f'<div style="font-size:20px;">📝</div>'
        f'</div>'

        f'<div style="flex:1;">'
        f'<div style="font-weight:600;color:{title_color};font-size:14px;margin-bottom:4px;">'
        f'Generating slides — {progress_text}</div>'
        f'<div style="font-size:12px;color:{sub_color};">{status} · {elapsed_str}</div>'
        f'{chips_row}'
        f'</div>'

        f'</div>'
    )


def _render_completed_state(progress: dict) -> None:
    """Show a completion summary with step bar and a button to proceed."""
    dark = st.session_state.get("dark_mode", True)
    st.markdown(step_progress_html(_PIPELINE_STEPS, len(_PIPELINE_STEPS), dark=dark), unsafe_allow_html=True)
    done = progress.get("topics_enriched", 0)
    elapsed = int(time.monotonic() - progress["started_at"])
    title = progress.get("doc_title", "Module")
    bank = progress.get("bank")
    q_count = len(bank.questions) if bank else 0
    st.success(f"**{title}** — {done} slide(s) and {q_count} quiz question(s) generated in {elapsed}s.")
    if st.button("Start Learning →", type="primary", key="_btn_go_learn_top"):
        _handle_completed(progress)


def _render_failed_state(progress: dict, elapsed: int) -> None:
    step = progress.get("failed_step", "")
    error_msg = progress.get("error", "An unexpected error occurred.")
    error_detail = progress.get("error_detail", "")
    partial_topics = progress.get("enriched_topics", [])
    partial_module = progress.get("module")
    partial_bank = progress.get("bank")

    st.markdown(
        f"""<div style="padding:16px 20px;background:#FEF2F2;border:1px solid #FECACA;border-left:4px solid #EF4444;border-radius:10px;margin-bottom:12px;">
  <div style="font-weight:700;color:#991B1B;font-size:15px;margin-bottom:4px;">Generation failed</div>
  <div style="color:#7F1D1D;font-size:14px;">{error_msg}</div>
  <div style="font-size:11px;color:#9CA3AF;margin-top:8px;">Step: <b>{step or 'unknown'}</b> · {elapsed}s elapsed</div>
</div>""",
        unsafe_allow_html=True,
    )

    if error_detail:
        with st.expander("Technical details"):
            st.code(error_detail, language=None)

    can_recover = (
        (step in ("quiz", "save") and partial_module is not None) or
        (step == "enrich" and len(partial_topics) >= 1)
    )

    if can_recover:
        n = len(partial_module.topics) if partial_module is not None else len(partial_topics)
        col_recover, col_retry = st.columns(2)
        with col_recover:
            if st.button(f"Learn with {n} slide(s) →", type="primary", key="_btn_recover"):
                if partial_module is None:
                    from backend.content.models import LearningModule
                    partial_module = LearningModule(
                        module_id=progress["module_id"],
                        title=progress.get("doc_title", "Partial Module"),
                        source_doc_id=progress.get("doc_id", ""),
                        topics=list(partial_topics),
                        created_at=datetime.now(timezone.utc).isoformat(),
                    )
                st.session_state["module"] = partial_module
                if partial_bank:
                    st.session_state["bank"] = partial_bank
                st.session_state["page"] = "tutor_room"
                _cleanup_pipeline_state()
                st.rerun()
        with col_retry:
            if st.button("Retry from scratch", type="secondary", key="_btn_retry_fail"):
                _cleanup_pipeline_state()
                st.rerun()
    else:
        cached_name = st.session_state.get("_cached_upload_name")
        if cached_name:
            st.caption(f"File **{cached_name}** will be re-used on retry.")
        if st.button("Retry", type="primary", key="_btn_retry"):
            _cleanup_pipeline_state()
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

    # Clear stale module data so the new module loads fresh
    for key in (
        "module", "bank", "quiz", "quiz_answers", "quiz_result",
        "tutor_state", "tutor_phase", "tutor_graph",
        "tutor_content_map", "tutor_visited_concepts", "chat_history",
        "all_modules", "pipeline_progress",
    ):
        st.session_state.pop(key, None)

    if bank:
        st.session_state["bank"] = bank
    if module is not None:
        st.session_state["module"] = module
        st.session_state["page"] = "learn"
    else:
        st.session_state["page"] = "module_library"
    _cleanup_pipeline_state()
    st.rerun()



def _prefetch_diagnostic(llm, doc, progress: dict) -> Future:
    """Prefetch diagnostic questions for the first topic in a background thread.

    Runs in parallel with slide 1 enrichment so questions are ready at redirect.
    """
    from concurrent.futures import ThreadPoolExecutor
    from backend.interactive_tutor.graph import _DIAGNOSTIC_SCHEMA, _DIAGNOSTIC_SYSTEM

    # Build a representative content sample from across the whole document
    # (not just the first section title, which may be a page code like "M1L1")
    all_body = "\n\n".join(
        s.body for s in doc.sections if s.body.strip()
    )
    content_sample = all_body[:1500].strip() or doc.title

    def _fetch():
        try:
            result = llm.generate(
                prompt=(
                    f"Document title: {doc.title}\n\n"
                    f"Content excerpt:\n{content_sample}\n\n"
                    "Generate 3 diagnostic questions to assess the student's prior knowledge "
                    "of the subject matter in this document. Base questions strictly on the "
                    "concepts mentioned in the content above."
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
        # Mark state immediately so the page shows "aborted" on next render
        # without waiting for the background thread to notice.
        progress = st.session_state.get("pipeline_progress")
        if progress:
            progress["state"] = "aborted"
        st.rerun()


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
