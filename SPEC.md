# SPEC.md — AI Tutor System Specification

> **Version:** 0.13 | **Last updated:** 2026-06-19
> Architecture, directory layout, and component design are in [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 0. Release Phases

| Phase | Name | Status | Key additions |
|-------|------|--------|---------------|
| 1 | PDF POC | ✅ Complete | Role-based access, Anthropic-only, SQLite, persistent module library |
| 2 | Functional Skeleton | ✅ Complete | LLM factory, MCP servers, LangGraph tutor, JIT pipeline, audio, observability |
| 3 | Refined Platform | 🔄 In Progress | Feature polish, admin-curated module library, PPTX/DOCX, full ChromaDB wiring |

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

### Phase 3 — Refined Platform 🔄 In Progress

**Goal:** Polish all Phase 2 features to production quality, close the remaining integration gaps, and add admin-curated module sharing and broader document format support.

**Scope:**

| Task | Description | Status |
|---|---|---|
| Admin mode (Phase 32) | Two-mode login: regular usernames log in as today (no password); usernames in `AI_TUTOR_ADMIN_USERNAMES` must additionally match `AI_TUTOR_ADMIN_PASSWORD` to set `is_admin=True`. Admin-generated modules can be published (copied) to a shared `published_modules` table in `data/shared/ai_tutor.db`, visible to all users in a "Shared Library" section. Admin scope is publish/unpublish of their own modules only — no edit/delete rights over other users' personal modules. Additonally in the login page create two separate set of login and password fields for admin and user modes. Password is only enabled for admin mode and user mode its disabled by default| ✅ Done |
| ChromaDB tutor wiring (Phase 34) | `provide_hint` queries `storage_server.query_vector_db` (filtered by `module_id`) to ground hints in retrieved chunks, non-fatal on error. `present_concept` queries ChromaDB only as a fallback when `enriched_topic`/`concept_content` is empty in state, using the concept title as query text — avoids redundant queries on the normal (pipeline-enriched) fast path. | ✅ Done |
| MCPClient pipeline integration (Phase 39) | Route `save_module_to_db` through `mcp_client` (storage_server gains an optional `db_path` param, delegates to `backend.analytics.db.get_db` + `persistence.save_module`, same pattern as Phase 30's `extract_text_from_pdf`). | ✅ Done |
| Portkey / Ollama validation | End-to-end test matrix: all three providers × PDF upload → module → tutor session | 🔲 Planned |
| LangGraph tutor polish (Phase 33/40) | Mastery persistence across sessions via a `tutor_sessions` table (serialized `GraphState` + UI phase); per-topic mastery written to `topic_mastery` table; mastery report page with cohort mastery analytics | ✅ Done |
| PPTX / DOCX parsing (Phase 35) | `pptx_parser.py`, `docx_parser.py` in `backend/ingestion/`; upload page accepts `.pptx` and `.docx`; MCP `document_server` exposes `extract_text_from_pptx`/`extract_text_from_docx` | ✅ Done |
| Audio improvements | Pre-generate audio for all topics (not just on-demand); cache invalidation on re-generation | 🔲 Planned |
| Observability dashboard (Phase 37) | Dedicated Streamlit page: Phoenix link + DeepEval per-session metric table + avg score bar chart; nav from sidebar and module library home page | ✅ Done |
| Error handling polish (Phase 36) | Structured user-facing error messages at each pipeline step; retry buttons; partial-failure recovery. Pipeline: per-step try/except (parse/LLM/enrich/quiz/save) with `_fail()` helper, step label, technical expander, and "Learn with N topic(s) / Retry from scratch" recovery buttons. Tutor: `_run_node` catches graph exceptions → `tutor_error` in session state → "Try again / Reset session" UI. Single-topic enrichment failure skips that topic instead of killing the pipeline. | ✅ Done |
| Test coverage (Phase 38) | MCP server tool tests (assessment validate_json_schema; document_server PPTX/DOCX); all LangGraph graph nodes tested with mock LLM; sliding pipeline end-to-end + skip-on-error | ✅ Done |
| UI/UX overhaul (Phase 41) | Dark mode (per-user persisted toggle, CSS-injection based since Streamlit config.toml can't be switched per-user at runtime); topic-highlighting "where am I" indicators (concept rail in the adaptive tutor, tabs per topic in the early module view); consistent top-of-page back navigation on every page; refined indigo/blue/purple color system with a new teal accent and matching dark palette | ✅ Done |
| Dark mode bug fixes (Phase 45) | Fixed invisible secondary-button text at rest (no resting-state rule existed, only `:hover`); fixed a systemic `.stButton > button` direct-child selector that silently stopped matching whenever Streamlit inserts a tooltip wrapper div (any button with `help=`) — affected the sign-out button and any future help-enabled button, in both themes; re-themed the sidebar from indigo to violet/purple; fixed unselected `st.tabs()` text being invisible in dark mode. The reported "can't re-expand collapsed sidebar" turned out to be a Streamlit 1.58.0 framework-level issue (reproduces in a vanilla app, unrelated to this codebase's CSS) — see Open Questions. | ✅ Done |

**Definition of done for Phase 3:**
- [x] Admin user can publish a module to the shared library; all other users see it in their module library without generating it themselves
- [x] `provide_hint` retrieves supporting context from ChromaDB; `present_concept` falls back to ChromaDB when pipeline-enriched content is unavailable in state
- [x] `save_module_to_db` is routed through `mcp_client` (PDF parsing and vector-store upsert already are, per Phase 29/30)
- [ ] End-to-end test passes for Portkey and Ollama providers
- [x] Mastery state is persisted across sessions (user can resume a tutor session)
- [x] Upload page accepts `.pptx` and `.docx` in addition to `.pdf`
- [x] All pipeline failures surface a structured, user-actionable error message
- [x] Dark mode toggle persists per-user and is legible (WCAG-checked) across every page
- [x] Every page has a single, consistent top-of-page back affordance
- [x] Adaptive tutor and module viewer show a clear position/progress indicator among topics

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
- [x] **Embedding model** — **Resolved:** Local `all-MiniLM-L6-v2`, run via ChromaDB's built-in ONNX `DefaultEmbeddingFunction` (`onnxruntime`), not `sentence-transformers`/`torch` — `torch` has no wheel for Python 3.13 on Intel macOS. Fully offline.
- [x] **LangGraph checkpointer** — **Resolved Phase 3 (superseded):** `tutor_room.py` invokes graph nodes manually via `_run_node()`, never through `graph.invoke(state, config=...)`, so a real `SqliteSaver` checkpointer (which hooks `.invoke()`/`config`/`thread_id`) doesn't fit without rewriting the tutor's control flow. **New resolution (Phase 33):** a lightweight `tutor_sessions` table stores the serialized `GraphState` dict + UI phase, keyed by `(user_id, module_id)`, upserted after each settled render and deleted on session completion — achieves "resume a tutor session" without a checkpointer.
- [x] **PPTX/DOCX priority** — **Resolved:** PDF only for Phase 2; PPTX/DOCX in Phase 3.
- [x] **Hint generation strategy** — **Resolved:** LLM-generated at runtime. `provide_hint` node receives question + context + specific error from evaluation.
- [x] **Diagnostic quiz** — **Resolved:** 3 MCQ questions before first slide; score sets `presentation_depth` (beginner / intermediate / advanced).
- [x] **MCP client architecture (Phase 29/30)** — **Resolved:** `backend/core/mcp_client.py` is a synchronous wrapper around the official `mcp` SDK's stdio client. Each `MCPClient` spawns its server subprocess once (via a background asyncio loop thread) and is reused for all calls — avoids repeated ChromaDB/onnxruntime import cost. A module-level `get_client(server_name)` returns a lazily-created singleton per server (`storage_server`, `document_server`, `assessment_server`).
- [x] **document_server PDF parsing schema (Phase 30)** — **Resolved:** `extract_text_from_pdf` delegates to `backend.ingestion.pdf_parser.parse_pdf` and returns `Document.to_json()`, so the MCP tool's output is a drop-in for `Document.from_json()` used by the pipeline. The previous divergent PyMuPDF-based implementation is removed.
- [x] **Portkey/Ollama Phase 2 validation scope** — **Resolved:** No live Ollama install or real Portkey key is available in the dev environment, so Phase 2 validation is mocked unit tests for `PortkeyAdapter`/`OllamaAdapter.generate()` plus a manual validation checklist recorded in `references.md` for the user to run later against live services.
- [x] **Admin mode granularity (Phase 32)** — **Resolved:** Admin can publish/unpublish their own generated modules only — no edit/delete rights over other users' personal modules. Admin identity: usernames in `AI_TUTOR_ADMIN_USERNAMES` must additionally provide `AI_TUTOR_ADMIN_PASSWORD` at login to set `is_admin=True`; non-admin usernames log in as before (no password). Published modules are copied into a new shared DB (`data/shared/ai_tutor.db`, table `published_modules`); personal per-user `modules` rows get an `is_published` flag for UI badge state.
- [x] **ChromaDB tutor-wiring scope (Phase 34)** — **Resolved:** `provide_hint` retrieves context via `query_vector_db` (filtered by `module_id`, query = student's feedback/struggle) to ground hints; non-fatal on error. `present_concept` queries ChromaDB only when `enriched_topic`/`concept_content` is empty in state (fallback path), using the concept title as query text — the normal pipeline-enriched fast path is unchanged.
- [x] **save_module_to_db MCP routing (Phase 39)** — **Resolved:** `storage_server.save_module_to_db` gains an optional `db_path` param and delegates to `backend.analytics.db.get_db(db_path)` + `backend.analytics.persistence.save_module(...)` (same delegation pattern as Phase 30's `extract_text_from_pdf`). `frontend/upload_page.py` calls it via `mcp_client` instead of importing `persistence.save_module` directly.
- [x] **Per-topic mastery tracking (Phase 33)** — **Resolved:** the existing-but-previously-unused `topic_mastery` table (`user_id, module_id, topic_id, mastered, difficulty, attempts, last_updated`) is written incrementally during a tutor session — once per concept, when it's mastered (or, if the session ends mid-concept, an "in progress" row with `mastered=0`). This is in addition to the end-of-session binary blob already stored in `user_profiles.topic_mastery_json`.
- [x] **Mastery report page (Phase 40)** — **Resolved:** a standalone `frontend/mastery_report_page.py`, reachable via a "Mastery Report" button per module in the Module Library ("My Modules" section) — viewable any time, not tied to quiz completion. Shows the user's per-topic mastery status/difficulty/attempts plus a cohort comparison (% of all users who mastered each topic) computed from `topic_mastery`.
- [x] **PPTX/DOCX parsing (Phase 35)** — **Resolved:** `backend/ingestion/pptx_parser.py` (`parse_pptx`, max 16 slides, title from `core_properties` or filename stem, each slide → `Section`) and `backend/ingestion/docx_parser.py` (`parse_docx`, max 16 sections, sections from heading paragraphs, fallback to single section when no headings). Both return `Document` with the matching `SourceType`. MCP `document_server` exposes `extract_text_from_pptx`/`extract_text_from_docx` tools following the same pattern as `extract_text_from_pdf`. `frontend/upload_page.py` accepts `["pdf", "pptx", "docx"]` and routes to the right tool via `_TOOL_FOR_EXT`.
- [x] **Observability dashboard (Phase 37)** — **Resolved:** `frontend/observability_page.py` with two sections: (1) Phoenix trace explorer — derives base URL from `OTEL_EXPORTER_OTLP_ENDPOINT`, shows `st.link_button` to open Phoenix UI; (2) DeepEval quality metrics — queries `eval_results` via `get_eval_results()` in `stats.py` (LEFT JOIN modules for title), renders per-session table + avg score bar chart. Navigation: "Observability" sidebar button + "📊 Observability" button on module library home page.
- [ ] **Portkey virtual key management** — One shared virtual key or per-user? **Pending.**
- [x] **Dark mode persistence & theming mechanism (Phase 41)** — **Resolved:** Streamlit's `[theme]` in `.streamlit/config.toml` is process-wide and can't be switched per-user at runtime (one shared server, many users), so dark mode is implemented entirely via the existing custom-CSS-injection mechanism (`frontend/styles.py::inject_global_css()`), gated on `st.session_state["dark_mode"]`. Persisted per-user via a new `user_profiles.dark_mode` column (same idempotent `_MIGRATIONS` pattern as `llm_provider`), restored on login alongside the existing LLM-provider preference restore.
- [x] **Color direction for the visual refresh (Phase 41)** — **Resolved:** keep the existing indigo/blue (`#2563EB`)/purple (`#7C3AED`) brand identity rather than replace it; add one new teal accent (`#14B8A6`) for variety/highlights, and a matching dark palette (`#0F1117` app bg / `#1A1D29` card bg / `#F1F5F9` text). User-confirmed direction over two more vibrant/warmer alternatives.
- [x] **Module viewer topic display (Phase 41)** — **Resolved:** `frontend/module_viewer.py` converts its stacked always-expanded `st.expander` list to `st.tabs()` (one per topic) — gives an always-visible topic index for free and avoids per-topic expand/collapse state tracking as topics stream in during generation. Accepted tradeoff: `st.tabs()` has no overflow/scroll handling for very large topic counts (typical modules are well under 10 topics).
- [ ] **Sidebar can't be re-expanded once collapsed (Phase 45)** — Confirmed via a vanilla Streamlit app (same installed version, zero custom CSS) that `[data-testid="stSidebarCollapseButton"]` is `visibility:hidden` by default and never becomes visible/reachable via hover at any point along the page edge, with or without this app's styling — this is a Streamlit 1.58.0 framework-level issue, not caused by the dark-mode CSS. A real fix would require injecting JS (e.g. via `streamlit.components.v1.html` with `window.parent.document` access) to add a custom always-visible toggle that calls the hidden button's `.click()` — a new technique for this codebase. **Pending a decision**: live with it, build the JS workaround, or try a Streamlit version bump first to see if it's already fixed upstream.

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
| `AI_TUTOR_DB_DIR` | Per-user DB directory (`<dir>/<username>/ai_tutor.db`) | `data` |
| `AI_TUTOR_SHARED_DB_PATH` | Shared DB for published modules (Phase 32) | `data/shared/ai_tutor.db` |
| `AI_TUTOR_ADMIN_USERNAMES` | Comma-separated admin usernames (Phase 32) | — |
| `AI_TUTOR_ADMIN_PASSWORD` | Required password for admin usernames (Phase 32) | — |
| `AI_TUTOR_UPLOAD_DIR` | Upload directory | `data/uploads` |
| `AI_TUTOR_MAX_FILE_MB` | Max upload size | `50` |
| `AI_TUTOR_CHROMA_PATH` | ChromaDB persistence directory | `data/chroma` |
| `AI_TUTOR_TOKEN_BUDGET` | Max tokens per generation run | `200000` |
| `PHOENIX_COLLECTOR_ENDPOINT` | Arize Phoenix OTEL endpoint | `http://localhost:6006/v1/traces` |
| `LANGCHAIN_API_KEY` | LangSmith API key (optional tracing) | — |
| `LANGCHAIN_TRACING_V2` | Enable LangSmith export | `false` |
