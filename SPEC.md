# SPEC.md — AI Tutor System Specification

> **Version:** 0.10 | **Last updated:** 2026-06-15
> Architecture, directory layout, and component design are in [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 0. Release Phases

| Phase | Name | Status | Key additions |
|-------|------|--------|---------------|
| 1 | PDF POC | ✅ Complete | Role-based access, Anthropic-only, SQLite, persistent module library |
| 2 | Functional Skeleton | ✅ Complete | LLM factory, MCP servers, LangGraph tutor, JIT pipeline, audio, observability |
| 3 | Refined Platform | 🔲 Planned | Feature polish, admin-curated module library, PPTX/DOCX, full ChromaDB wiring |

---

### Phase 1 — PDF POC ✅ COMPLETE

**Delivered in:** `main` branch (Phases 1–16 commits)

Single Anthropic provider, PDF-only input, SQLite persistence, Streamlit frontend with role-based access.

**Scope delivered:**
- Two roles: **Admin** (password-protected) uploads PDFs and generates modules; **Users** consume modules
- Full 5-stream pipeline: PDF ingestion → LLM content generation → Mermaid diagrams → Quiz engine → Analytics
- Persistent module library: modules survive restarts, reusable across sessions
- Quiz with selectable difficulty (easy / medium / hard), randomised questions, per-question explanations
- Cohort analytics: score vs. min/max/avg of all participants shown on results page
- Demo mode: sidebar toggle loads fixture JSON, bypasses all LLM calls
- All five work streams integrated and tested end-to-end

**Definition of done:** ✅ All items delivered.

---

### Phase 2 — Functional Skeleton ✅ Complete

**Delivered in:** `changes-to-use-langgraph-evals-audio` branch (Phases 17–28 commits)

**Goal:** Build a working skeleton for every planned platform capability. All major features must be implemented and runnable end-to-end, even if rough around the edges. Refinement is explicitly deferred to Phase 3.

**Features delivered so far (Phases 17–28):**

| Feature | Description | Status |
|---|---|---|
| Codebase restructure | `backend/` + `frontend/` + `mcp_servers/` layered architecture | ✅ Done |
| LLM Factory | Multi-provider factory: Anthropic, Portkey, Ollama (OpenAI-compat) | ✅ Done |
| MCP tool servers | `document_server`, `assessment_server`, `storage_server` as standalone MCP processes | ✅ Done |
| Background pipeline | Daemon thread for content generation; abort support; progress tracking | ✅ Done |
| Sliding-window decomposition | 500-word assessment windows; force-publish fallbacks; immediate per-topic publishing | ✅ Done |
| Just-in-time delivery | Redirect after topic 1 enriched; `@st.fragment(run_every=3)` polling; deferred quiz button | ✅ Done |
| Diagram-first slides | Generate visual anchor (Mermaid or bullet fallback) before writing explanation | ✅ Done |
| Audio/TTS narration | `edge-tts` narration per topic; audio toggle; slide timer synced to audio duration | ✅ Done |
| LangGraph adaptive tutor | Diagnostic quiz → calibrate depth → slide presentation → Q&A loop | ✅ Done |
| Per-user DB + login page | Separate login page; per-user preferences (provider, model) stored in SQLite | ✅ Done |
| System check page | Verify installed packages and environment variables before running | ✅ Done |
| DeepEval quality evals | Async LLM-as-judge quality metrics fired at end of each tutor session | ✅ Done |
| Arize Phoenix tracing | OTEL spans sent to local Phoenix instance; LangChain + Anthropic SDK instrumented | ✅ Done |
| ChromaDB integration | `mcp_client.py` (Phase 29) calls `storage_server.upsert_to_vector_db` after each topic enrichment; `query_vector_db` verified by test | ✅ Done |
| Portkey / Ollama testing | Adapters implemented; validated via mocked unit tests (Phase 31); live e2e deferred to Phase 3 | ✅ Done |
| MCPClient wired to pipeline | PDF parsing now dispatched via `mcp_client` → `document_server.extract_text_from_pdf` (Phase 30) | ✅ Done |

**Definition of done for Phase 2:**
- [x] `LLMFactory.create("portkey" | "ollama" | "anthropic")` returns a working client
- [x] Three MCP servers each expose their tools
- [x] Direct LLM pipeline produces a `LearningModule` with JIT delivery
- [x] LangGraph tutor compiles and runs diagnostic → slides → Q&A → hint/simplify loop
- [x] Audio narration plays per slide with auto-advance timer
- [x] DeepEval evals run asynchronously at end of session
- [x] ChromaDB stores and retrieves chunks by semantic similarity (enriched topics upserted in `sliding_pipeline.py`; round-trip verified in `tests/test_mcp/test_storage_server.py`. Querying *during* a LangGraph tutor session remains Phase 3 / Phase 34.)
- [x] `mcp_client.py` is used by the content pipeline (not just standalone) — PDF parsing in `upload_page.py` now calls `document_server.extract_text_from_pdf` via `mcp_client.get_client()`. Full replacement of all direct pipeline calls remains Phase 3 / Phase 30 follow-on (see Phase 3 scope).
- [x] Portkey and Ollama adapters validated end-to-end (mocked unit tests for `generate()` and `make_cached_document_blocks()` in `tests/test_content/test_llm_client.py`; live end-to-end validation against real Ollama/Portkey services is deferred to Phase 3 per the manual checklist in `references.md`)

---

### Phase 3 — Refined Platform 🔲 Planned

**Goal:** Polish all Phase 2 features to production quality, close the remaining integration gaps, and add admin-curated module sharing and broader document format support.

**Scope:**

| Task | Description |
|---|---|
| Admin mode | Admin-generated modules are published to a shared library visible to all users. Regular users can still generate personal modules. Adds `is_published` flag on modules and admin publish/unpublish controls. |
| ChromaDB full wiring | Wire semantic retrieval into the LangGraph `present_concept` node to fetch topic content; wire into `provide_hint` for context-aware hints |
| MCPClient pipeline integration | Replace direct function calls in content pipeline with `mcp_client.call()` dispatches to MCP servers |
| Portkey / Ollama validation | End-to-end test matrix: all three providers × PDF upload → module → tutor session |
| LangGraph tutor polish | Mastery persistence across sessions (`SqliteSaver` checkpointer); mastery report page; cohort mastery analytics |
| PPTX / DOCX parsing | `pptx_parser.py`, `docx_parser.py` in `backend/ingestion/`; upload page accepts `.pptx` and `.docx` |
| Audio improvements | Pre-generate audio for all topics (not just on-demand); cache invalidation on re-generation |
| Observability dashboard | Expose Arize Phoenix and DeepEval results in a dedicated Streamlit page |
| Error handling polish | Structured user-facing error messages at each pipeline step; retry buttons; partial-failure recovery |
| Test coverage | Integration tests for MCP servers, LLM factory adapters, and LangGraph graph |

**Definition of done for Phase 3:**
- [ ] Admin user can publish a module to the shared library; all other users see it in their module library without generating it themselves
- [ ] LangGraph `present_concept` node retrieves content from ChromaDB (not from session state)
- [ ] `mcp_client.py` is the sole integration point between pipeline steps and MCP servers
- [ ] End-to-end test passes for Portkey and Ollama providers
- [ ] Mastery state is persisted across sessions (user can resume a tutor session)
- [ ] Upload page accepts `.pptx` and `.docx` in addition to `.pdf`
- [ ] All pipeline failures surface a structured, user-actionable error message

---

## 1. Non-Functional Requirements

### 1.1 File Constraints
- Max upload: 50 MB
- Phase 2: `.pdf` only; Phase 3 adds `.pptx` and `.docx`

### 1.2 LLM Usage
- All LLM calls go through `BaseLLMClient` — no direct SDK imports outside `adapters/`
- Token budget per module generation: 200,000 tokens (configurable via `AI_TUTOR_TOKEN_BUDGET`)
- Timeout per call: 60 seconds; retry once on transient failure

### 1.3 Performance
- Time to first topic visible: ~20–40 seconds (parse + decompose + enrich 1 topic)
- Full module generation: 1–3 minutes total
- Quiz assembly (no LLM): < 1 s
- LangGraph node invocation: < 10 s per turn
- ChromaDB query: < 500 ms

### 1.4 Security
- No passwords for local development — username-only identification
- Admin identified by configured password (same as Phase 1 approach)
- API keys read from env; never logged or committed

---

## 2. Open Questions

- [x] **Content pipeline approach** — **Resolved:** Sliding-window decomposition + direct LLM calls with typed tool schemas.
- [x] **Embedding model** — **Resolved:** Local `sentence-transformers` (`all-MiniLM-L6-v2`). Fully offline.
- [x] **LangGraph checkpointer** — **Resolved Phase 3:** `SqliteSaver` (built-in, zero extra infra).
- [x] **PPTX/DOCX priority** — **Resolved:** PDF only for Phase 2; PPTX/DOCX in Phase 3.
- [x] **Hint generation strategy** — **Resolved:** LLM-generated at runtime. `provide_hint` node receives question + context + specific error from evaluation.
- [x] **Diagnostic quiz** — **Resolved:** 3 MCQ questions before first slide; score sets `presentation_depth` (beginner / intermediate / advanced).
- [x] **MCP client architecture (Phase 29/30)** — **Resolved:** `backend/core/mcp_client.py` is a synchronous wrapper around the official `mcp` SDK's stdio client. Each `MCPClient` spawns its server subprocess once (via a background asyncio loop thread) and is reused for all calls — avoids repeated ChromaDB/sentence-transformers import cost. A module-level `get_client(server_name)` returns a lazily-created singleton per server (`storage_server`, `document_server`, `assessment_server`).
- [x] **document_server PDF parsing schema (Phase 30)** — **Resolved:** `extract_text_from_pdf` delegates to `backend.ingestion.pdf_parser.parse_pdf` and returns `Document.to_json()`, so the MCP tool's output is a drop-in for `Document.from_json()` used by the pipeline. The previous divergent PyMuPDF-based implementation is removed.
- [x] **Portkey/Ollama Phase 2 validation scope** — **Resolved:** No live Ollama install or real Portkey key is available in the dev environment, so Phase 2 validation is mocked unit tests for `PortkeyAdapter`/`OllamaAdapter.generate()` plus a manual validation checklist recorded in `references.md` for the user to run later against live services.
- [ ] **Admin mode granularity** — Should admin also be able to edit or delete other users' generated modules, or only publish/unpublish? **Pending user confirmation.**
- [ ] **Portkey virtual key management** — One shared virtual key or per-user? **Pending.**

---

## Appendix A: Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `AI_TUTOR_LLM_PROVIDER` | `anthropic` \| `portkey` \| `ollama` | `anthropic` |
| `AI_TUTOR_LLM_API_KEY` | Anthropic or Portkey API key | (required) |
| `AI_TUTOR_LLM_MODEL` | Model name | `claude-sonnet-4-6` |
| `AI_TUTOR_PORTKEY_VIRTUAL_KEY` | Portkey virtual key | — |
| `AI_TUTOR_OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `AI_TUTOR_DB_PATH` | SQLite file path | `data/ai_tutor.db` |
| `AI_TUTOR_UPLOAD_DIR` | Upload directory | `data/uploads` |
| `AI_TUTOR_MAX_FILE_MB` | Max upload size | `50` |
| `AI_TUTOR_CHROMA_PATH` | ChromaDB persistence directory | `data/chroma` |
| `AI_TUTOR_TOKEN_BUDGET` | Max tokens per generation run | `200000` |
| `PHOENIX_COLLECTOR_ENDPOINT` | Arize Phoenix OTEL endpoint | `http://localhost:6006/v1/traces` |
| `LANGCHAIN_API_KEY` | LangSmith API key (optional tracing) | — |
| `LANGCHAIN_TRACING_V2` | Enable LangSmith export | `false` |
