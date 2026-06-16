# plan.md — AI Tutor Implementation

> **Goal:** Deliver a fully working AI Tutor with adaptive tutoring, observability, and admin-curated module sharing.
> **Spec:** SPEC.md v0.7
> **Last updated:** 2026-06-15

---

## Phase 1 — PDF POC ✅ COMPLETE (main branch)

All original Phases 1–16 committed to `main`. Full end-to-end flow: PDF → LLM → module → quiz → analytics.

---

## Phase 2 — Functional Skeleton (this branch: `changes-to-use-langgraph-evals-audio`)

Goal: build a working skeleton for every planned capability. Rough edges allowed — Phase 3 polishes.

### Completed sub-phases

| Phase | Description | Status |
|---|---|---|
| Phase 17 | Parallelise content pipeline (concurrent topic enrichment) | ✅ Done |
| Phase 18 | Fast redirect + progressive enrichment + wait engagement | ✅ Done |
| Phase 19 | Sliding-window decomposition: 500-word assess, publish immediately | ✅ Done |
| Phase 20 | Fix sliding pipeline: lower threshold, add force-publish fallbacks | ✅ Done |
| Phase 21 | Per-user DB, per-user LLM preferences, file memory on retry | ✅ Done |
| Phase 22 | Separate login page, redirect bug fix, model dropdown from env | ✅ Done |
| Phase 23 | Hide sidebar on login, slide transition, 60s auto-advance, LLM prefs in DB | ✅ Done |
| Phase 24 | Cleanup: remove redundant files, update .gitignore, add .env.copy template | ✅ Done |
| Phase 25 | Consolidate LLM helpers into `backend/core/` | ✅ Done |
| Phase 26 | Diagram-first slide generation: anchor (Mermaid or bullet fallback) before explanation | ✅ Done |
| Phase 27 | Fix audio latency; sync slide timer to audio duration | ✅ Done |
| Phase 28 | Fix repeated diagnostic audio on slide 1; add audio toggle | ✅ Done |

### Remaining Phase 2 work

#### Phase 29 — ChromaDB end-to-end wiring ✅ Done

Created `backend/core/mcp_client.py`: a synchronous `MCPClient` wrapping the `mcp` SDK stdio client, with each server subprocess started once (background asyncio loop thread) and reused; `get_client(server_name)` returns a lazy singleton. Wired `storage_server.upsert_to_vector_db` into the content pipeline so enriched topics are stored in ChromaDB after generation (both publish points in `run_sliding_pipeline`, via `_store_in_vector_db`, non-fatal on error). Verified `query_vector_db` returns correct chunks via tests.

**Files:**
- `backend/core/mcp_client.py` (new) — `MCPClient`, `get_client()`
- `backend/content/sliding_pipeline.py` — `_store_in_vector_db()` called after each topic enrichment (both publish points), with `module_id`/`topic_id`/`title`/`order` metadata
- `tests/test_mcp/test_mcp_client.py`, `tests/test_mcp/test_storage_server.py` (new)
- `pyproject.toml` — registered `slow` pytest marker for the ChromaDB round-trip test

---

#### Phase 30 — MCPClient pipeline integration ✅ Done

Made `document_server.extract_text_from_pdf` delegate to `backend.ingestion.pdf_parser.parse_pdf` and return `Document.to_json()` (schema parity with `Document.from_json`). Replaced the direct `parse_pdf()` call in `upload_page._run_pipeline_bg` with `get_client("document_server").call("extract_text_from_pdf", ...)` → `Document.from_json(...)`.

**Files:**
- `mcp_servers/document_server/server.py` — now a thin wrapper over `parse_pdf`
- `frontend/upload_page.py` — PDF parsing routed through `mcp_client`
- `tests/test_mcp/test_document_server.py` (new) — verifies MCP output matches direct `parse_pdf()` output

---

#### Phase 31 — Portkey + Ollama validation (mocked, Phase 2 scope) ✅ Done

Removed dead duplicated `coerce_tool_array`/`coerce_tool_item` from `anthropic_adapter.py` (unused, missing `import json` — the real versions live in `base.py`/`__init__.py`). Added mocked unit tests for `PortkeyAdapter.generate()` (plain text, tool-schema → dict, `make_cached_document_blocks`) and `OllamaAdapter.generate()` (tool_calls path with `_fix_stringified_values`, JSON-extraction fallback for plain/fenced/brace-matched content, `{"parameters": ...}` unwrapping, plain-text response). No bugs surfaced — both adapters behaved correctly against all mocked cases. Added a `## LLM Provider Validation` section to `references.md` documenting mocked coverage plus a manual checklist for live Ollama/Portkey validation.

**Files:**
- `backend/core/llm_client/adapters/anthropic_adapter.py` — removed dead code (lines 80-106)
- `tests/test_content/test_llm_client.py` — added Portkey/Ollama `generate()` tests
- `references.md` — new "LLM Provider Validation" section

---

**Phase 2 status: ✅ Complete** — all three remaining DoD items (Phases 29, 30, 31) are done. See SPEC.md §0 and §Phase 2 for details.

## Phase 3 — Refined Platform 🔄 In Progress

Goal: production-quality polish and the admin module library feature.

### Phase 32 — Admin mode: published module library ✅ Done

Two-mode login: the login page has separate **"User Login"** and **"Admin Login"** tabs, each with their own username field. The User Login tab's password field is disabled (greyed out, "Not required for regular users") — submitting it logs in as a regular user with no admin checks, regardless of whether the username happens to be in `AI_TUTOR_ADMIN_USERNAMES`. The Admin Login tab has an enabled, required password field; submitting validates `is_admin_username(name)` ("This username is not registered as an admin." if not) and `check_admin_password(password)` ("Incorrect admin password." if not) — on success `st.session_state["is_admin"] = True`. Both tabs share a `_do_login(name, is_admin)` helper for the common DB lookup/creation, session-state population, and redirect. Admins can publish/unpublish their own modules — `publish_module` copies the module+question-bank JSON into a new shared DB (`data/shared/ai_tutor.db`, table `published_modules`) and sets `is_published=1` on the personal `modules` row; `unpublish_module` reverses both. The Module Library page now has two sections: "My Modules" (with a Published badge and, for admins, Publish/Unpublish buttons) and "Shared Library" (all published modules, with a "Learn" button that loads directly from the shared DB). The sidebar shows "(Admin)" next to the username when `is_admin` is set.

**Files:**
| File | Change |
|---|---|
| `backend/analytics/db.py` | `is_published` column migration on `modules`; new `get_shared_db()` opening `data/shared/ai_tutor.db` (`AI_TUTOR_SHARED_DB_PATH` override) with `published_modules` table |
| `backend/analytics/auth.py` (new) | `is_admin_username()`, `check_admin_password()` against `AI_TUTOR_ADMIN_USERNAMES`/`AI_TUTOR_ADMIN_PASSWORD` |
| `backend/analytics/persistence.py` | `publish_module`, `unpublish_module`, `get_published_modules`, `load_published_module`; `list_modules` now returns `is_published` |
| `frontend/login_page.py` | Two-tab login ("User Login" / "Admin Login") with shared `_do_login()` helper; admin-gate logic via `backend.analytics.auth` |
| `frontend/module_library_page.py` | "My Modules" (badge + admin publish/unpublish) + "Shared Library" sections |
| `app.py` | Sidebar shows "(Admin)" when `st.session_state["is_admin"]` |
| `.env`, `.env.copy` | New `AI_TUTOR_ADMIN_USERNAMES`, `AI_TUTOR_ADMIN_PASSWORD`, `AI_TUTOR_SHARED_DB_PATH` |
| `tests/test_analytics/test_persistence.py`, `tests/test_analytics/test_auth.py` (new) | Publish/unpublish round-trip + admin auth helper tests |

---

### Phase 33 — Tutor session resume + per-topic mastery persistence ✅ Done

`tutor_room.py` invokes graph nodes manually via `_run_node()`, never `graph.invoke(state, config=...)`, so a real `SqliteSaver` checkpointer doesn't fit without rewriting the tutor's control flow (see SPEC.md §2, superseded resolution). Instead: a new `tutor_sessions` table stores the serialized `GraphState` dict + UI phase, keyed by `(user_id, module_id)`. On entering the tutor room, if a non-"done" saved session exists for this user/module, restore it and show a "Resuming your previous session" banner with a "Restart from scratch" option; otherwise initialize fresh as before. After every settled render, upsert the current state/phase (or delete the row once `phase == "done"`). Separately, the existing-but-unused `topic_mastery` table (`user_id, module_id, topic_id, mastered, difficulty, attempts, last_updated`) is now written to incrementally — once per concept when it's mastered (slide auto-advance or Q&A success), and as an "in progress" (`mastered=0`) row if the session ends mid-concept.

**Files:**
- `backend/analytics/db.py` — new `tutor_sessions` table
- `backend/analytics/persistence.py` — `save_tutor_session`, `load_tutor_session`, `delete_tutor_session`, `save_topic_mastery`, `get_topic_mastery`
- `frontend/tutor_room.py` — resume-on-entry, `_persist_session`, `_record_topic_mastery` helpers wired into the slide/Q&A/end-session flows
- `tests/test_analytics/test_persistence.py` — round-trip tests for the new functions

---

### Phase 40 — Mastery report page + cohort mastery analytics ✅ Done

New standalone page showing a user's per-topic mastery (mastered / in progress / not started, difficulty reached, attempts) for a module, plus a cohort comparison (% of all users who mastered each topic), reachable via a "Mastery Report" button per module in the Module Library — viewable any time, not tied to quiz completion.

**Files:**
- `backend/analytics/models.py` — `TopicMasteryRow`, `MasteryReport`, `CohortTopicMastery`, `CohortMastery` dataclasses
- `backend/analytics/stats.py` — `get_mastery_report`, `get_cohort_mastery`
- `frontend/mastery_report_page.py` (new) — per-topic badges + cohort bar chart, following `results_page.py`'s layout conventions
- `frontend/module_library_page.py` — "Mastery Report" button per module
- `app.py` — new `mastery_report` page route
- `tests/test_analytics/test_stats.py` — tests for the new mastery stats functions

---

### Phase 34 — ChromaDB wired into LangGraph tutor ✅ Done

Added `_retrieve_context(module_id, query_text, n_results)` to `graph.py`: calls `storage_server.query_vector_db` via `mcp_client` (filtered by `module_id`), joins the returned chunks, and returns `""` on any error (non-fatal, same pattern as `_store_in_vector_db`). `provide_hint` prepends retrieved context (queried with the student's feedback, or the concept title if no feedback) to its prompt. `present_concept` calls `_retrieve_context` with the concept title only when `enriched_topic`/`concept_content` is empty in state, and feeds the result into the existing pipeline-enriched fast path (so depth-adaptation/audio logic is unchanged).

**Files:**
- `backend/interactive_tutor/graph.py` — `_retrieve_context`, wired into `provide_hint` and `present_concept`
- `tests/test_tutor/__init__.py`, `tests/test_tutor/test_graph_chromadb.py` (new) — retrieval-grounded hint, fallback slide content, non-fatal error handling

---

### Phase 35 — PPTX + DOCX parsing ✅ Done

`parse_pptx` (max 16 slides, title from `core_properties` or filename stem, each slide body from non-title placeholder text, blank-body slides skipped) and `parse_docx` (max 16 sections, groups paragraphs by heading style, falls back to one section if no headings). MCP `document_server` exposes `extract_text_from_pptx`/`extract_text_from_docx` delegating to the new parsers. `upload_page.py` accepts `["pdf", "pptx", "docx"]` and routes to the right MCP tool via `_TOOL_FOR_EXT`.

**Files:**
- `backend/ingestion/pptx_parser.py` (new)
- `backend/ingestion/docx_parser.py` (new)
- `backend/ingestion/__init__.py` — export new parsers
- `frontend/upload_page.py` — multi-format uploader + `_TOOL_FOR_EXT` routing
- `mcp_servers/document_server/server.py` — add `extract_text_from_pptx`, `extract_text_from_docx`
- `tests/test_ingestion/test_pptx_parser.py`, `tests/test_ingestion/test_docx_parser.py` (new)
- `pyproject.toml` — added `python-pptx`, `python-docx`

---

### Phase 36 — Error handling and UX polish ✅ Done

Structured, user-actionable error messages at each pipeline step. Retry buttons. Partial-failure recovery (save topics that succeeded even if later steps fail).

**Files:**
- `backend/content/sliding_pipeline.py` — `_enrich_one`: guard `enrich()` with try/except so a single bad topic is skipped (returns `None`) rather than killing the pipeline
- `frontend/upload_page.py` — `_fail()` helper; per-step try/except in `_run_pipeline_bg` (parse, LLM connect, enrich, quiz, save); `progress["module"]` set early after enrichment; failed-state UI with step label, collapsible technical expander, and "Learn with N topic(s) / Retry from scratch" two-column recovery buttons

---

### Phase 37 — Observability dashboard ✅ Done

Dedicated page (`frontend/observability_page.py`) with two sections: (1) Phoenix trace explorer with `st.link_button` to open the Phoenix UI (base URL derived from `OTEL_EXPORTER_OTLP_ENDPOINT`); (2) DeepEval quality metrics — per-session table + avg score bar chart, queried via `get_eval_results()` in `backend/analytics/stats.py` (LEFT JOIN modules for module title). Navigation added to sidebar ("Observability" button) and module library home page ("📊 Observability" button in header row).

**Files:**
- `frontend/observability_page.py` (new) — Phoenix section + DeepEval section
- `backend/analytics/stats.py` — `get_eval_results(user_id, limit, db)` (note: placed in stats.py, not eval_runner.py, for consistency with other query functions)
- `app.py` — sidebar button + router case
- `frontend/module_library_page.py` — "📊 Observability" button in header

---

### Phase 38 — Test coverage

Integration tests for MCP servers, LLM factory adapters, and the LangGraph graph (dry-run with mock LLM responses).

**Files:**
- `tests/test_mcp/` — test each MCP server tool in subprocess mode
- `tests/test_llm_client/` — test all three adapters against a mock endpoint
- `tests/test_tutor/` — test graph compilation and node state transitions

---

### Phase 39 — MCPClient pipeline integration: save_module_to_db ✅ Done

`storage_server.save_module_to_db` gained an optional `db_path` param and now delegates to `backend.analytics.db.get_db(db_path)` + `backend.analytics.persistence.save_module(...)` (same delegation pattern as Phase 30's `extract_text_from_pdf` → `parse_pdf`), so the per-user DB's schema and migrations are applied. The dead `_get_db`/`_DB_PATH` helpers (previously raw `INSERT OR REPLACE` SQL against a fixed `AI_TUTOR_DB_PATH`) were removed. `frontend/upload_page.py`'s save-to-database step now calls `mcp_client.get_client("storage_server").call("save_module_to_db", ..., db_path=db_path)` instead of importing `persistence.save_module`/`db.get_db` directly.

**Files:**
- `mcp_servers/storage_server/server.py` — `save_module_to_db` delegates via `db_path` param; removed unused `_get_db`/`_DB_PATH`
- `frontend/upload_page.py` — save step routed through `mcp_client`; removed unused `save_module`/`get_db` imports
- `tests/test_mcp/test_storage_server_persistence.py` (new) — round-trips a module through the MCP tool and `persistence.load_module`

---

## Commit convention

Format: `[Phase N] <short description>`
Use the `/git-commit` skill after each phase — never run `git commit` directly.
