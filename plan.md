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

## Phase 3 — Refined Platform 🔲 Planned

Goal: production-quality polish and the admin module library feature.

### Phase 32 — Admin mode: published module library

Add `is_published` flag to modules. Admin user can publish/unpublish a module, making it visible to all users without them generating it themselves.

**Scope:**
- DB migration: add `is_published INTEGER DEFAULT 0` to `modules` table
- `backend/analytics/persistence.py` — `publish_module(module_id)`, `unpublish_module(module_id)`, `get_published_modules()`
- `frontend/module_library_page.py` — show published modules to all users; show publish/unpublish controls only to admin
- Admin is identified by a configured admin username (or existing password mechanism from Phase 1)
- Personal modules remain private to the generating user unless published

**Files:**
| File | Change |
|---|---|
| `backend/analytics/db.py` | Add `is_published` column migration |
| `backend/analytics/persistence.py` | `publish_module`, `unpublish_module`, `get_published_modules` |
| `frontend/module_library_page.py` | Published section visible to all; admin controls |
| `frontend/app.py` | Propagate `is_admin` flag into session state |
| `backend/content/models.py` | Add `is_published: bool = False` to `LearningModule` |

---

### Phase 33 — LangGraph mastery persistence + mastery report

Wire `SqliteSaver` as the LangGraph checkpointer so sessions resume after page refresh. Add a mastery report page.

**Files:**
- `backend/interactive_tutor/graph.py` — add `SqliteSaver` checkpointer
- `backend/analytics/db.py` — `topic_mastery` table (see SPEC §7.5)
- `backend/analytics/stats.py` — `get_mastery_report`, `get_cohort_mastery`
- `frontend/` — new `mastery_report_page.py` (or section in results)

---

### Phase 34 — ChromaDB wired into LangGraph tutor

Replace `concept_content` injection from session state with a ChromaDB `query_vector_db` call inside `present_concept`. Wire `provide_hint` to retrieve additional context chunks.

**Files:**
- `backend/interactive_tutor/nodes.py` — `present_concept` calls `storage_server.query_vector_db`
- `backend/interactive_tutor/nodes.py` — `provide_hint` retrieves supporting chunks from ChromaDB

---

### Phase 35 — PPTX + DOCX parsing

Implement `pptx_parser.py` and `docx_parser.py`. Update upload page to accept `.pptx` and `.docx`. Output must conform to the same `Document` / `Section` contracts as the PDF parser.

**Files:**
- `backend/ingestion/pptx_parser.py`
- `backend/ingestion/docx_parser.py`
- `frontend/upload_page.py` — expand file type filter
- `mcp_servers/document_server/` — add `extract_text_from_pptx`, `extract_text_from_docx` tools

---

### Phase 36 — Error handling and UX polish

Structured, user-actionable error messages at each pipeline step. Retry buttons. Partial-failure recovery (save topics that succeeded even if later steps fail).

**Files:**
- `backend/content/sliding_pipeline.py` — per-step error capture and publish
- `frontend/upload_page.py` — surface step-specific errors with retry controls
- `frontend/tutor_room.py` — graph error → reset session with checkpoint restore offer

---

### Phase 37 — Observability dashboard

Expose Arize Phoenix and DeepEval results in a dedicated Streamlit page. Link to Phoenix UI, show per-session eval summary, trend charts.

**Files:**
- `frontend/observability_page.py` (new)
- `backend/observability/eval_runner.py` — add `get_eval_results(user_id)` query
- `frontend/app.py` — add page to router

---

### Phase 38 — Test coverage

Integration tests for MCP servers, LLM factory adapters, and the LangGraph graph (dry-run with mock LLM responses).

**Files:**
- `tests/test_mcp/` — test each MCP server tool in subprocess mode
- `tests/test_llm_client/` — test all three adapters against a mock endpoint
- `tests/test_tutor/` — test graph compilation and node state transitions

---

## Commit convention

Format: `[Phase N] <short description>`
Use the `/git-commit` skill after each phase — never run `git commit` directly.
