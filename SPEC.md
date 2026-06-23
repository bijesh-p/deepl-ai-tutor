# SPEC.md — AI Tutor System Specification

> **Version:** 0.30 | **Last updated:** 2026-06-23
> Architecture, directory layout, and component design are in [ARCHITECTURE.md](ARCHITECTURE.md).
> **GUI / frontend requirements are specified in [gui_spec.md](gui_spec.md)** — that document
> is authoritative for all GUI features, normative UI decisions (dark-theme default, button
> consistency), and suggested frontend improvements.

---

## 0. Release Phases

| Phase | Name | Status | Key additions |
|-------|------|--------|---------------|
| 1 | PDF POC | ✅ Complete | Role-based access, Anthropic-only, SQLite, persistent module library |
| 2 | Functional Skeleton | ✅ Complete | LLM factory, MCP servers, LangGraph tutor, JIT pipeline, audio, observability |
| 3 | Refined Platform | 🔄 In Progress | Feature polish, admin-curated module library, PPTX/DOCX, full ChromaDB wiring |
| 4 | VTT Transcript Ingestion | 🔲 Planned | Parse training/classroom `.vtt` transcripts into learning modules |

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
| Portkey / Ollama validation | End-to-end test matrix: all three providers × PDF upload → module → tutor session | ✅ Done |
| LangGraph tutor polish (Phase 33/40) | Mastery persistence across sessions via a `tutor_sessions` table (serialized `GraphState` + UI phase); per-topic mastery written to `topic_mastery` table; mastery report page with cohort mastery analytics | ✅ Done |
| PPTX / DOCX parsing (Phase 35) | `pptx_parser.py`, `docx_parser.py` in `backend/ingestion/`; upload page accepts `.pptx` and `.docx`; MCP `document_server` exposes `extract_text_from_pptx`/`extract_text_from_docx` | ✅ Done |
| Audio improvements | Pre-generate audio for all topics (not just on-demand); cache invalidation on re-generation | 🔲 Planned |
| Observability dashboard (Phase 37) | Dedicated Streamlit page: Phoenix link + DeepEval per-session metric table + avg score bar chart; nav from sidebar and module library home page | ✅ Done |
| Error handling polish (Phase 36) | Structured user-facing error messages at each pipeline step; retry buttons; partial-failure recovery. Pipeline: per-step try/except (parse/LLM/enrich/quiz/save) with `_fail()` helper, step label, technical expander, and "Learn with N topic(s) / Retry from scratch" recovery buttons. Tutor: `_run_node` catches graph exceptions → `tutor_error` in session state → "Try again / Reset session" UI. Single-topic enrichment failure skips that topic instead of killing the pipeline. | ✅ Done |
| Test coverage (Phase 38) | MCP server tool tests (assessment validate_json_schema; document_server PPTX/DOCX); all LangGraph graph nodes tested with mock LLM; sliding pipeline end-to-end + skip-on-error | ✅ Done |
| UI/UX overhaul (Phase 41) | Dark mode (per-user persisted toggle, CSS-injection based since Streamlit config.toml can't be switched per-user at runtime); topic-highlighting "where am I" indicators (concept rail in the adaptive tutor, tabs per topic in the early module view); consistent top-of-page back navigation on every page; refined indigo/blue/purple color system with a new teal accent and matching dark palette | ✅ Done |
| Dark mode bug fixes (Phase 45) | Fixed invisible secondary-button text at rest (no resting-state rule existed, only `:hover`); fixed a systemic `.stButton > button` direct-child selector that silently stopped matching whenever Streamlit inserts a tooltip wrapper div (any button with `help=`) — affected the sign-out button and any future help-enabled button, in both themes; re-themed the sidebar from indigo to violet/purple; fixed unselected `st.tabs()` text being invisible in dark mode. The reported "can't re-expand collapsed sidebar" turned out to be a Streamlit 1.58.0 framework-level issue (reproduces in a vanilla app, unrelated to this codebase's CSS) — see Open Questions. | ✅ Done |
| Streamlit upgrade + Windows/Linux audit (Phase 46) | Confirmed no Streamlit upgrade is possible (already on latest stable, 1.58.0); the sidebar-collapse bug is a recurring upstream issue with no fix version to wait for, not something this app's CSS caused. Removed the now-fully-confirmed-dead `stSidebarCollapsedControl` CSS (pre-1.38 testid name, renamed to `stSidebarCollapseButton`) from both `frontend/styles.py` and `frontend/login_page.py`. Audited `pyproject.toml`/`uv.lock` for Windows/Linux platform risk — none found beyond the already-handled `onnxruntime` pin. | ✅ Done |
| Sidebar collapse/expand JS workaround (Phase 47) | New `frontend/sidebar_toggle.py::render_sidebar_toggle()` — a small always-visible custom button rendered via `st.iframe()`, forwarding clicks to Streamlit's hidden native sidebar control via `window.parent.document`. Pinned to the page edge via a new `[data-testid="stIFrame"]` rule in `_GLOBAL_CSS`. Theme-aware (violet in dark mode, indigo/blue in light). Resolves the Phase 45/46 open question. | ✅ Done |
| UI polish round 2 (Phase 48) | Re-themed sidebar dark palette from violet to neutral slate-gray (`_DARK_PALETTE` + `sidebar_toggle.py`). Fixed quiz radio/checkbox options becoming invisible on hover/select in dark mode — the unconditional light `:hover`/`:has(input:checked)` backgrounds in `_GLOBAL_CSS` combined with near-white dark-mode text to produce near-white-on-near-white; added dark-appropriate hover/checked colors. Fixed the login page's "AI Tutor" title rendering outside its white card — the card was built by opening a `<div>` in one `st.markdown()` call and closing it in a later, separate call, which Streamlit doesn't nest content inside; replaced with `st.container(key="login_canvas")`, which gives every element rendered in the `with` block a real shared parent. | ✅ Done |
| Configurable max topic limit | A numeric "Max topics" input on the upload page lets the user cap how many topics/slides the pipeline generates from the uploaded document. When set (e.g. 5), the pipeline selects the N most important topics from the document and terminates after enriching them — useful for quick demos or targeted study. When set to 0 or left blank, the pipeline generates topics for the entire document (current default behaviour). The limit applies uniformly to all document types (PDF, PPTX, DOCX, VTT). Implemented as: (1) `st.number_input` on the upload page, stored in `session_state["max_topics"]`; (2) passed through to `sliding_pipeline.run()` which truncates the decomposed topic list to the configured cap before enrichment begins; (3) parsers' existing `max_slides`/`max_sections` defaults (16) remain unchanged — the new cap operates at the pipeline level after decomposition, not at the parser level. Default: 0 (unlimited / generate all). Environment-variable override: `AI_TUTOR_DEFAULT_MAX_TOPICS` sets the default value shown in the input. | 🔲 Planned |

**Definition of done for Phase 3:**
- [x] Admin user can publish a module to the shared library; all other users see it in their module library without generating it themselves
- [x] `provide_hint` retrieves supporting context from ChromaDB; `present_concept` falls back to ChromaDB when pipeline-enriched content is unavailable in state
- [x] `save_module_to_db` is routed through `mcp_client` (PDF parsing and vector-store upsert already are, per Phase 29/30)
- [x] End-to-end test passes for Portkey and Ollama providers
- [x] Mastery state is persisted across sessions (user can resume a tutor session)
- [x] Upload page accepts `.pptx` and `.docx` in addition to `.pdf`
- [x] All pipeline failures surface a structured, user-actionable error message
- [x] Dark mode toggle persists per-user and is legible (WCAG-checked) across every page
- [x] Every page has a single, consistent top-of-page back affordance
- [x] Adaptive tutor and module viewer show a clear position/progress indicator among topics
- [ ] Upload page exposes a "Max topics" numeric input; when set to N > 0 the pipeline generates at most N topics; when 0 or blank it generates all topics from the document

---

### Phase 4 — VTT Transcript Ingestion 🔲 Planned

**Goal:** Allow users to upload WebVTT (`.vtt`) training or classroom recording transcripts and transform them into interactive learning modules — same experience as PDF/PPTX/DOCX uploads. The parser must extract **teaching content and key concepts** (not raw conversation), capture **important Q&A exchanges**, and **never record speaker/participant names** (privacy).

**Background:** Training sessions and classroom lectures are often recorded and auto-transcribed into `.vtt` (WebVTT) subtitle files by platforms like Zoom, Teams, Google Meet, and YouTube. These transcripts contain rich spoken content but are hard to learn from in raw form — they are timestamped caption streams with speaker turns, filler words, and no structural organisation. This phase parses VTT files into the existing `Document`/`Section` model so the full enrichment pipeline (decompose → enrich → diagrams → audio → quiz → tutor) works unchanged.

**Scope:**

| Task | Description | Status |
|---|---|---|
| VTT parser | `backend/ingestion/vtt_parser.py` — `parse_vtt(path, max_sections=16)` reads a `.vtt` file, strips timestamps/cue formatting/speaker names, and produces a clean `Document`. **Content extraction:** (1) Identify teaching/instructional content (explanations, definitions, walkthroughs) vs. non-content chatter (greetings, logistics, "can you hear me?"). (2) Detect Q&A exchanges — questions asked during the session and their answers — and preserve them as dedicated sections or inline within the relevant topic section. **Privacy:** All speaker/participant names are stripped from the output — sections are titled by topic/concept, never by person (e.g. `"Topic: Neural Network Basics"`, `"Q&A: Backpropagation"`, not `"Speaker: John"`). **Segmentation:** Split on topic/concept shifts detected from content flow, with time-gap (>30 s) as a secondary signal, and ~500-word fixed chunking as final fallback. Returns a `Document` with `source_type=SourceType.VTT`. | 🔲 Planned |
| SourceType enum | Add `VTT = "vtt"` to `backend/ingestion/models.py::SourceType` | 🔲 Planned |
| MCP document_server tool | Expose `extract_text_from_vtt` in `mcp_servers/document_server/` — delegates to `vtt_parser.parse_vtt`, returns `Document.to_json()` (same pattern as PDF/PPTX/DOCX tools) | 🔲 Planned |
| Upload page integration | Add `"vtt"` to the accepted file types in `frontend/upload_page.py`; route `.vtt` uploads to `extract_text_from_vtt` via the existing `_TOOL_FOR_EXT` dispatch map | 🔲 Planned |
| Unit tests | `tests/test_ingestion/test_vtt_parser.py` — parse a fixture `.vtt` file with speaker turns, verify section count/titles/body; edge cases: no speakers, single cue, empty file. `tests/test_mcp/test_document_server_vtt.py` — MCP round-trip test | 🔲 Planned |

**VTT parsing details:**

1. **Format support:** Standard WebVTT (RFC 8216 §3.5) — `WEBVTT` header, optional cue identifiers, `HH:MM:SS.mmm --> HH:MM:SS.mmm` timestamps, cue payloads. HTML tags (`<b>`, `<i>`, `<v>`) and `NOTE` blocks are stripped.
2. **Privacy — no speaker names in output:** Speaker tags (`<v Name>`, `Speaker N:`) are used internally to detect turn boundaries and Q&A patterns, but are **never** included in the output `Section.title` or `Section.body`. Section titles use topic/concept labels (e.g. `"Topic: Data Pipelines"`, `"Q&A: Error Handling"`), not person names. Any remaining names embedded in cue text are replaced with generic labels (`"Instructor"`, `"Participant"`).
3. **Content extraction — teaching focus:** The parser classifies cue content into three categories:
   - **Teaching content** (keep, high priority): Explanations, definitions, examples, demonstrations, walkthroughs, conceptual discussions.
   - **Q&A exchanges** (keep, tagged): Questions asked by participants and the instructor's answers. These are preserved and grouped — either as a dedicated `"Q&A: <topic>"` section or appended to the relevant topic section with a `"---\n**Q&A**\n"` separator.
   - **Non-content chatter** (discard): Greetings, roll call, "can you hear me?", "let me share my screen", scheduling logistics, repeated filler phrases. Stripped during cleanup.
4. **Section boundaries:** (a) Topic/concept shift detected from content flow (keyword signals: "let's move on to", "next topic", "now let's talk about", subject-matter change). (b) Q&A block detected (question pattern followed by answer). (c) Time gap >30 s between cues as secondary signal. (d) Final fallback: ~500-word fixed chunking → sections titled `"Part N"`.
5. **Text cleanup:** Strip timestamps, cue IDs, HTML tags, `NOTE` comments, `STYLE` blocks, and speaker identity markers. Collapse filler phrases and repeated words from auto-transcription. Preserve paragraph breaks at cue boundaries.
6. **Limits:** Max 16 sections (consistent with PPTX/DOCX). `total_pages` set to number of sections (VTT has no page concept).

**Definition of done for Phase 4:**
- [ ] `SourceType.VTT` exists in models.py
- [ ] `parse_vtt()` returns a valid `Document` from a `.vtt` file
- [ ] Output sections are titled by topic/concept — **no speaker names** appear anywhere in the `Document`
- [ ] Teaching content (explanations, concepts, examples) is extracted and non-content chatter is discarded
- [ ] Q&A exchanges from the session are captured and preserved (as dedicated sections or inline with topic)
- [ ] `parse_vtt()` handles the no-speaker fallback (time-gap and fixed-chunk segmentation)
- [ ] `extract_text_from_vtt` MCP tool is exposed and callable via `mcp_client`
- [ ] Upload page accepts `.vtt` files and routes them through the existing pipeline
- [ ] A `.vtt` upload produces a complete learning module (topics + quiz + tutor session)
- [ ] Unit tests pass for parser, Q&A extraction, name stripping, and MCP round-trip

---

## 1. Non-Functional Requirements

### 1.1 File Constraints
- Max upload: 50 MB
- Phase 2: `.pdf` only; Phase 3 adds `.pptx` and `.docx`; Phase 4 adds `.vtt`
- **Max topics per module:** Configurable via a numeric input on the upload page. When set to N > 0, the pipeline generates at most the N most important topics from the document. When 0 or blank, all topics are generated (default). Env-var default: `AI_TUTOR_DEFAULT_MAX_TOPICS` (default `0`). Applies to all document types uniformly.

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
- [x] **Sidebar can't be re-expanded once collapsed (Phase 45/46/47)** — **Resolved via custom JS workaround.** Root cause: `[data-testid="stSidebarCollapseButton"]` is `visibility:hidden` by default and never becomes reachable via hover in Streamlit 1.58.0 — a framework-level issue (confirmed in a vanilla app; no newer Streamlit version exists to fix it; recurring class of bug in Streamlit's own issue tracker going back to 1.25/1.38). Fix: `frontend/sidebar_toggle.py::render_sidebar_toggle()` renders a small always-visible button via `st.iframe()` (the non-deprecated successor to `components.v1.html`), pinned to the page's top-left edge via CSS (`[data-testid="stIFrame"]` in `_GLOBAL_CSS`). On click, the button's own JS reaches into the parent page via `window.parent.document` and calls `.click()` on the real (hidden) native control — this works because `.click()` triggers React's handler regardless of CSS visibility, only *mouse*-driven interaction was blocked. Verified live: toggles the sidebar open/closed reliably in both light and dark mode (themed to match), not rendered on the login page (no sidebar there), zero console errors.
- [x] **Windows/Linux dependency compatibility audit (Phase 46)** — **Resolved, no issues found:** the only active platform-specific pin is `onnxruntime<1.24` for `sys_platform == 'darwin' and platform_machine == 'x86_64'` (Intel-Mac-only; Windows/Linux resolve to the newer unconstrained `onnxruntime==1.26.0`). `pymupdf` has full prebuilt-wheel coverage (`cp310-abi3`, valid through Python 3.14 on regular builds) for Windows, macOS, and Linux (x86_64 + arm64) — no build-from-source risk. `sqlean-py` (transitive) already has an automatic Windows/non-Windows split in `uv.lock`. No OS-specific code anywhere in this project's own source. Gap noted, not fixed: no CI/`.github/workflows`, so this is a static dependency-metadata audit, not a live cross-platform test run.
- [x] **Wrapping multiple Streamlit elements in one styled container (Phase 48)** — **Resolved:** opening a `<div>` via `st.markdown()` and closing it in a *later, separate* `st.markdown()` call does not nest the content rendered in between — Streamlit renders each call as an independent sibling, so the browser auto-closes the unclosed div immediately and nothing (not even immediately-following content) ends up inside it. The correct pattern is `with st.container(key="some_key"):` — every element rendered inside the `with` block becomes a real DOM child of one shared wrapper carrying the CSS class `st-key-some_key`, which can then be styled directly. Used to fix the login page's title-outside-its-card bug; this is the general pattern to reach for whenever custom CSS needs to wrap a mix of markdown and native widgets.
- [x] **VTT transcript ingestion (Phase 4)** — **Resolved:** `backend/ingestion/vtt_parser.py` parses WebVTT files with three key requirements: (1) **Extract teaching content** — identify concepts, explanations, walkthroughs, and discard non-content chatter (greetings, logistics). (2) **Capture Q&A** — detect question-answer exchanges from the session and preserve them as tagged sections. (3) **Privacy** — strip all speaker/participant names; sections titled by topic, never by person. Segmentation: topic shifts > time gaps (>30 s) > ~500-word fixed chunking. Returns the standard `Document`/`Section` model with `SourceType.VTT`. No new dependencies — VTT is plain text parsed with regex. MCP tool and upload-page integration follow the same pattern as PPTX/DOCX (Phase 35).
- [x] **Merging `main` (VTT ingestion, e2e tests, diagram/tutor robustness fixes) with `experiment/improve-ui` (dark mode toggle, navigation, topic highlighting) (Phase 49)** — **Resolved:** `main` had independently grown its own forced, permanent dark theme (`.streamlit/config.toml` `base = "dark"` + a single hardcoded-dark `_GLOBAL_CSS`, no toggle) while diverging — this is fully superseded by `experiment/improve-ui`'s per-user toggle system (light default + `_theme_overrides_css(dark)`), since the user asked to keep `main`'s functional features but take UI improvements like dark mode/navigation from the feature branch. `.streamlit/config.toml` was reverted to its light-default values to match. `frontend/module_viewer.py` required a manual (non-automatic) merge: kept `main`'s robustness — `_sanitize_mermaid` + try/except around broken diagrams, the top "Start Adaptive Tutor" button, and the sidebar "Contents" list (which also previews not-yet-generated topic titles, something the tabs view can't show) — while adopting `experiment/improve-ui`'s `st.tabs()` topic navigation and top-of-page back button. `app.py`, `frontend/login_page.py`, and `frontend/styles.py` took `experiment/improve-ui`'s versions, since `main`'s changes there were entirely the now-superseded forced-dark theme with no independent functional content. All other touched files (`results_page.py`, `tutor_room.py`, `upload_page.py`, `backend/analytics/persistence.py`, `db.py`, `README.md`) merged cleanly with both branches' features intact, verified by inspecting the merged result directly rather than trusting "no conflict" alone. Performed as a merge of `main` into `experiment/improve-ui` (not the other way around), so `main` is untouched until this branch is reviewed and fast-forwarded/merged in separately.
- [x] **Invisible "Upload" button text in dark mode (Phase 50)** — **Resolved:** `st.file_uploader`'s native "Browse files" button (`data-testid="stBaseButton-secondary"`, `kind="secondary"`) is rendered directly inside `[data-testid="stFileUploader"]`, not wrapped in a `.stButton` div — so the existing `.stButton button[kind="secondary"]` dark-mode fix (Phase 45) never matched it. With no rule of its own, its text inherited `color: {text_primary}` (near-white) from the page-wide `.stApp` dark-mode rule while its background stayed Streamlit's native white, producing white-on-white text. Fixed with a dedicated `[data-testid="stFileUploader"] button[kind="secondary"]` rule in `_theme_overrides_css()` using the same `card_bg`/`text_primary` tokens as every other secondary surface — verified live, contrast ratio 15.31:1 in dark mode, light mode pixel-unchanged.
- [x] **Missing `chromadb`/`deepeval` dependencies causing `ModuleNotFoundError` at runtime (Phase 51)** — **Resolved:** commit `ad72ea1` (pre-dating the Phase 49 merge, on `main`'s lineage) stripped `chromadb`, `deepeval`, `arize-phoenix`, and `sentence-transformers` from `pyproject.toml`'s dependency list during local debugging; only `sentence-transformers` was ever intentionally meant to stay removed (replaced by ChromaDB's built-in ONNX `DefaultEmbeddingFunction`, per the macOS-runtime-error fix). Because `experiment/improve-ui` never touched that dependency list, the Phase 49 merge silently inherited `main`'s deletion. `chromadb` is imported unguarded at module level in `mcp_servers/storage_server/server.py::_get_chroma_collection()` — every `upsert_to_vector_db`/`query_vector_db` MCP call raised `ModuleNotFoundError: No module named 'chromadb'` in production, silently breaking the ChromaDB-grounded-hints feature (caught and logged by `sliding_pipeline._store_in_vector_db`, so it degraded silently rather than crashing the pipeline). `deepeval` has the same gap but is already lazily imported inside a try/except in `backend/observability/eval_runner.py` (warns and no-ops), so it degraded more gracefully but was still silently broken. `arize-phoenix` was confirmed to have zero direct Python imports anywhere in this codebase (Phoenix runs as an external process; this app only needs the already-present `opentelemetry-exporter-otlp-proto-http`/`opentelemetry-sdk` to send spans to it) — correctly left out. Fixed via `uv add "chromadb>=1.5.9" "deepeval>=2.0.0"` (restoring the exact historical version constraints), verified by calling the actual previously-failing `upsert_to_vector_db`/`query_vector_db` MCP tools end-to-end through `mcp_client`.
- [x] **`StreamlitAPIException: Progress Value has invalid value [0.0, 1.0]: -0.1` on the quiz "← Previous" button (Phase 52)** — **Resolved:** `frontend/quiz_page.py`'s Prev/Next buttons guarded against going out of bounds with `disabled=(idx == 0)` / `disabled=is_last` — an equality check, not a `<=`/`>=` check — while the click handlers unconditionally did `ss["quiz_current_idx"] -= 1` / `+= 1` with no clamp. A rapid double-click sends two click events before the first rerun's disabled re-render reaches the browser: the first click takes `idx` from `0` to `-1`; on the next render `disabled=(idx == 0)` evaluates `False` (since `-1 != 0`), so the button renders enabled again and the second (already-queued) click decrements it again to `-2`. With a 10-question quiz, `st.progress((idx + 1) / total_q)` then computes `(-2 + 1) / 10 = -0.1`, exactly the reported value. Reproduced deterministically via `AppTest` by forcing `quiz_current_idx = -1` directly and confirming the "← Previous" button rendered enabled, then clicking it to hit the exact exception. Also would have caused `questions[idx]` to silently wrap to the wrong question via Python's negative indexing instead of erroring, for any `idx` that went negative but not far enough to break the progress bar. Fixed at the root: both click handlers now clamp the new index into `[0, total_q - 1]` (`max(0, idx - 1)` / `min(total_q - 1, idx + 1)`) and both `disabled` checks use `<=`/`>=` instead of `==`, so `quiz_current_idx` can never leave valid bounds regardless of click timing.
- [x] **Mermaid diagrams missing for some Adaptive Tutor slides (Phase 53)** — **Resolved, two contributing causes:** (1) `backend/interactive_tutor/graph.py::present_concept`'s two diagram-recovery paths (the "pipeline finished but produced no diagram" inline fallback, and the "pipeline hasn't enriched yet" lightweight-slide LLM call) only checked `if not mermaid_code:` — but `_sanitize_mermaid` always prepends a `flowchart TD` header to whatever it's given, so even empty or garbage LLM output comes back as a non-empty string (`"flowchart TD\n"`), making the truthiness check pass and letting a contentless diagram reach `st_mermaid()` to render blank or fail silently. (2) Even when correctly detected as unusable, neither path had a content fallback — unlike the main upload pipeline's `generate_slide_anchor`, which is documented to "hold either a Mermaid diagram or a bullet list — never both, never empty." Fixed by extracting the same node/edge validation `_try_diagram` already used into a reusable `is_valid_mermaid()` in `backend/content/diagram_generator.py` (used by both `_try_diagram` internally and the two `present_concept` call sites), and adding the same bullets-fallback (`_try_bullets`, prepended into the transcript) to both `present_concept` paths whenever no valid diagram results — mirroring `generate_slide_anchor`'s exact guarantee so a slide is never left with neither. Added `test_present_concept_fallback_uses_bullets_when_no_diagram` to cover the new behavior; updated the pre-existing `test_present_concept_fallback_calls_llm` (which used `mermaid_code: ""` to mean "no diagram, plain transcript pass-through") to use a real bracketed-node mermaid string instead, since under the new stricter validation its old empty-string fixture now correctly triggers the bullets fallback rather than being accepted as "valid".
- [x] **Tutor slide audio doesn't stop when switching slide/topic; quiz results page white-on-white question headers and black-on-black question text in dark mode (Phase 54)** — **Resolved, three issues:**
  1. **Audio doesn't stop:** Streamlit reruns synchronously — clicking "Next slide"/"Previous topic"/"Ask me a question" can trigger several seconds of LLM/audio-generation work before the new page (without the old `st.audio` element) reaches the browser. Verified via an isolated repro that `st.audio` itself replaces/removes its DOM element correctly across normal reruns (no leak there) — the actual gap is the **wait**: the old audio keeps playing client-side for however long the backend takes, since there's no server-side hook to reach back into an already-rendered page mid-rerun. Fixed with `frontend/audio_autostop.py::render_audio_autostop()` (called once at the top of `render_tutor_room()`), an invisible `st.iframe()` whose script adds a capture-phase click listener on `window.parent.document` that pauses any playing `<audio>` immediately on any button click, client-side, before the rerun completes. Verified live with autoplay actually enabled (`--autoplay-policy=no-user-gesture-required`): audio paused within ~150 ms of the click, well before a simulated 2 s backend delay finished.
  2. **White-on-white "Question N" headers:** the per-question `st.expander`'s own `<summary>` (clickable header) keeps Streamlit's native near-white background regardless of the outer dark background applied to `[data-testid="stExpander"]` — white text (inherited from `.stApp`) on that native background is white-on-white. Same "nested native element keeps its own background" pattern as the Phase 50 upload-button fix. Fixed by adding `[data-testid="stExpander"] summary { background: card_bg !important; }` to `_theme_overrides_css()`.
  3. **Black-on-black question text:** `frontend/results_page.py` hardcoded `color:#111827` on the question-text div with no background of its own — it sits directly on the expander's background, which is dark in dark mode. Fixed by computing a theme-aware `question_text_color` (mirrors the `header_text_color` pattern already used in `app.py`) instead of hardcoding it.
  All three verified live via a synthetic results-page harness (`AnswerResult`/`QuizResult` fixtures, no real quiz needed) — dark mode: header `rgb(241,245,249)` text on `rgb(26,29,41)` background, question text `rgb(241,245,249)` on transparent (inherits the same dark background); light mode confirmed pixel-unchanged. Full pytest suite: 139 passed, 0 failures (CSS/audio-only changes, no logic under test).
- [x] **`PYTHONPATH=. uv run phoenix serve` fails with "Failed to spawn: `phoenix`" (Phase 55)** — **Resolved:** Phase 51's restoration of dependencies dropped by `main`'s pre-merge lineage explicitly left `arize-phoenix` out, reasoning that it has zero direct Python imports in the codebase (Phoenix runs as an external process, reached only via the already-present `opentelemetry-exporter-otlp-proto-http` exporter). That reasoning missed that the README (and `observability_page.py`'s own caption) documents starting that external process via `PYTHONPATH=. uv run phoenix serve` — a CLI entry point provided by the `arize-phoenix` package itself, not by any OTEL exporter package. Without it installed in the `uv` venv, `uv run phoenix` has no `phoenix` console script to spawn. Fixed via `uv add arize-phoenix`, verified by running the exact documented command and confirming the server starts and serves the UI at `http://localhost:6006`.
- [x] **GUI overhaul: dark-theme default + button consistency (Phase 56–57)** — **Resolved.** (1) Dark theme is the single application default — `inject_global_css()` applies dark overrides on every page (including login); `dark_mode` seeded to `True` at startup in `app.py`; login page `_LOGIN_CSS` rewritten for dark palette. No light-theme flash on first load. (2) Dark-mode sidebar toggle and `save_dark_mode` call removed; Streamlit native top-right app menu restored. (3) All multi-button rows use equal-width `st.columns` with `use_container_width=True`; shared `min-height: 2.25rem` token in `.stButton button`; Module Library action row normalised to 4 equal columns (Publish column always rendered, empty for non-admins). Full pytest suite: 140 passed.

---

## 3. Bug Fixes — Navaneeth

Compiled from standalone change specs scoped under `changes/` via the `/spec-plan`
skill before implementation (see each `changes/<name>.spec.md` for full detail —
problem, current behavior, root cause, decisions, requirements, out of scope).

### Mermaid diagram rendering reliability

**Problem:** Diagram slides could show mermaid.js's raw `Syntax error in text
mermaid version ...` directly to the user, with no diagram and no fallback —
`st_mermaid()`'s failure happens client-side, after Python's call has already
returned successfully, so the existing `try/except` around it never caught
anything.

**Fix:** Replaced `streamlit-mermaid` with a custom renderer
(`frontend/mermaid_render.py`) that runs vendored mermaid.js + `svg-pan-zoom`
directly inside an `st.iframe()`, wrapped in a JS `try/catch`. On failure, it
falls back to the topic's existing `key_takeaways` bullets instead of
mermaid's error text. `key_takeaways` is threaded into `present_concept`'s
slide dict (previously only stored when no diagram was generated at all) so
every diagram-bearing slide also carries fallback content.

**Files:** `frontend/mermaid_render.py` (new),
`frontend/static/vendor/{mermaid.min.js,svg-pan-zoom.min.js}` (new),
`backend/interactive_tutor/graph.py`, `frontend/tutor_room.py`,
`frontend/module_viewer.py`; `streamlit-mermaid` removed from `pyproject.toml`.

### Mermaid render timeout (hung diagrams)

**Problem:** A diagram could render as a permanently blank box with no
fallback ever appearing — confirmed live on a topic with a cyclic flowchart
("Orchestrator-Subagent" pattern).

**Root cause:** `mermaid.render()`'s dagre/d3 layout phase can hang
indefinitely on syntactically-valid but structurally pathological graphs
(e.g. cycles) — a known class of issue in mermaid's own layout engine, not a
defect in this app's code.

**Fix:** The renderer's inline script races `mermaid.render()` against a
5-second timer; if the timer wins, the same bullets fallback shows (no
visual distinction from an error/rejection fallback). A late-resolving render
still replaces the fallback with the real diagram if it eventually succeeds.

**Files:** `frontend/mermaid_render.py`.

### Mermaid diagrams broken for every topic except the first

**Problem:** Every topic's diagram in the Module Viewer rendered as a
near-invisible speck (`viewBox="-8 -8 16 16"`, every text label measuring
`0×0`) except the first topic's.

**Root cause:** Streamlit's `st.tabs()` puts every tab panel into the DOM at
once, hiding inactive ones via CSS. Mermaid measures label text by
temporarily rendering it and reading its real pixel size — browsers return
zero for layout queries inside a hidden ancestor, so a diagram rendered while
its tab is inactive gets a permanently-baked-in zero-size layout (mermaid
never re-measures later when the tab becomes visible). Confirmed by direct
reproduction, independent of diagram content, pan/zoom, and the timeout fix
above.

**Fix:** The renderer's script now waits for an `IntersectionObserver` to
confirm the diagram's content is actually visible before calling
`mermaid.render()` for the first time — already-visible content (the common
case) renders with no perceptible delay; content in a hidden tab defers
rendering until the tab is opened. The 5s timeout now starts when rendering
is actually attempted, not at script load.

**Files:** `frontend/mermaid_render.py`.

### MCP client reliability: storage_server hang with no timeout

**Problem:** In the Adaptive Tutor, after answering all of a topic's
questions the app could hang indefinitely instead of advancing to the next
topic.

**Root cause:** `storage_server`'s first MCP tool call in a session pays a
one-time, highly variable (observed ~1s–30s+) cost importing
`chromadb`/`numpy` — likely antivirus/real-time-scan interference on native
extension loads (confirmed via `py-spy` stack-trace dumping of the hung
subprocess, stuck inside `numpy._core.multiarray` native loading).
`backend/core/mcp_client.py::MCPClient.call()` had no timeout at all, so a
slow import on this path could block the tutor's `present_concept` →
`_retrieve_context` call forever.

**Fix:** Added a 30-second timeout to `MCPClient.call()` (via
`future.result(timeout=...)`) as a safety net, plus a
`warm_up_storage_server()` background-thread pre-warm called once at app
startup (`app.py`), so the slow import cost is paid before a real user ever
reaches the tutor flow rather than synchronously on their critical path.

**Files:** `backend/core/mcp_client.py`, `app.py`. *(Implemented directly,
no standalone `changes/*.spec.md` — noted for the record since every other
entry above has one.)*

### Diagnostic quiz review screen

**Goal** (feature, not a bug — included here per compilation request):
the diagnostic quiz's "Submit & Start Learning" button immediately evaluated
answers and jumped straight to the lesson slide, with no feedback shown on
what the student got right or wrong.

**Fix:** Added a required `explanation` field to each diagnostic question
(`_DIAGNOSTIC_SCHEMA`/`_DIAGNOSTIC_SYSTEM` in `graph.py`) and a new
`diagnostic_review` UI phase (`frontend/tutor_room.py::_render_diagnostic_review`)
shown after every topic's diagnostic, before the lesson: overall score plus a
per-question breakdown (chosen answer, correct answer, ✅/❌, explanation),
with a "Continue to lesson →" button to proceed.

**Files:** `backend/interactive_tutor/graph.py`, `frontend/tutor_room.py`,
`tests/test_tutor/test_graph_nodes.py`.

### Bloom's-taxonomy-based question generation levels

**Goal** (feature, not a bug — included here per compilation request, scoped
via `/spec-plan` as `changes/bloom-taxonomy-question-generation.{spec,plan}.md`):
question generation across the app used an informal easy/medium/hard
difficulty scale with no grounding in a cognitive-skill model. Replace it
with proper Bloom's-taxonomy levels (remember, understand, apply, analyze,
evaluate, create), informed by Scaria et al., "Automated Educational
Question Generation at Different Bloom's Skill Levels using Large Language
Models" (AIED 2024) — specifically its PS2 prompting strategy (persona +
chain-of-thought + inline skill-level definitions), which the paper found
gave the best balance of quality and skill-adherence; adding hardcoded
few-shot examples on top (PS5) measurably hurt both, so none were added.

**Decisions:** all four question-generation flows (main quiz bank, inline
per-topic questions, diagnostic pre-assessment, tutor-room single question)
were updated. Bloom's level *replaces* difficulty everywhere — not tracked
alongside it. The end-of-module quiz mixes questions across all six levels
in every attempt (no per-attempt level picker); inline per-topic questions
are restricted to the first three levels (remember / understand / apply),
since those fit a quick comprehension check better than the higher-order
levels. The orphaned `BLOOMS_LEVELS`/`DIFFICULTY_MAP` in
`mcp_servers/assessment_server/server.py` was left untouched — not wired
into any real path, out of scope for this change.

**Fix:** `backend/quiz/models.py` gained `BLOOM_LEVELS` and renamed
`QuizQuestion.difficulty` → `bloom_level`; `Quiz.difficulty` was removed
entirely (quizzes are mixed-level, no single label). `backend/quiz/question_bank.py`'s
generation prompt and tool schema now ask for 18-24 questions covering all
six levels (≥3 per level) with the levels' definitions inline.
`backend/quiz/assembler.py` rewrote `assemble_quiz()` to bucket and sample
roughly evenly across all six levels with cross-level backfill, instead of
a single-difficulty filter. `frontend/quiz_page.py` replaced the
Easy/Medium/Hard card selector with a quiz-intro screen showing a per-level
question-count breakdown, and switched the per-question badge from one
quiz-wide difficulty tag to each question's own Bloom-level icon/label.
`backend/content/models.py::Question` gained `bloom_level` (defaulted for
backward-compat with modules persisted before this change), and
`backend/content/inline_question_gen.py` now tags each inline question with
one of the first three levels. `backend/interactive_tutor/graph.py`'s
diagnostic prompt now asks for a mix of Remember/Understand-level questions
only (pre-lesson, so higher levels aren't appropriate yet), and
`ask_question()`'s prompt maps `presentation_depth` (beginner/intermediate/advanced)
to a target Bloom's level pair instead of a vague "match the student's
level" instruction. `frontend/module_library_page.py` gained a legacy
difficulty→Bloom-level mapping so modules persisted before this change still
load instead of raising a `KeyError`.

**Files:** `backend/quiz/models.py`, `backend/quiz/question_bank.py`,
`backend/quiz/assembler.py`, `frontend/quiz_page.py`,
`frontend/module_library_page.py`, `frontend/results_page.py`,
`frontend/upload_page.py`, `app.py`, `backend/content/models.py`,
`backend/content/inline_question_gen.py`,
`backend/interactive_tutor/graph.py`,
`tests/test_quiz/test_assembler.py`, `tests/test_quiz/test_evaluator.py`,
`tests/test_content/test_inline_question_gen.py` (new),
`tests/test_content/test_pipeline.py`, `tests/test_e2e/test_provider_e2e.py`.
See [gui_spec.md](gui_spec.md) §3.6 for the updated Quiz UI checklist.

---

## 4. Bug Fixes — ported from `experiment/improve-ui`

- [x] **"Download Results" button white-on-white in dark mode (Phase 62)** — **Resolved:** same coverage gap as the Phase 50 upload-button fix, on a different native element. `st.download_button()` (`frontend/results_page.py:142`) renders inside `[data-testid="stDownloadButton"]`, not `.stButton`, so the existing `.stButton button[kind="secondary"]` dark-mode rule never matched it — the button kept Streamlit's native white background while its text inherited the page-wide dark `color: #F1F5F9` from `.stApp`. Fixed by adding a dedicated `[data-testid="stDownloadButton"] button[kind="secondary"]` rule to `_theme_overrides_css()` in `frontend/styles.py`, using the same `card_bg`/`text_primary` tokens as the upload-button fix. Verified live via a synthetic results-page harness: dark mode now resolves to `rgb(26,29,41)` background / `rgb(241,245,249)` text (was white-on-white); light mode confirmed pixel-unchanged (`rgb(255,255,255)` / `rgb(17,24,39)`). Full pytest suite: 139 passed, 0 failures.
- [x] **Module Library shows uploaded file as `tmpXXXXXX.<ext>` instead of the original filename (Phase 63)** — **Resolved:** `Document.source_filename` (set by every parser in `backend/ingestion/*_parser.py` as `path.name`) was always derived from the `tempfile.NamedTemporaryFile` path the upload form writes the bytes to before parsing — never from the user's actual filename. `frontend/upload_page.py`'s `save_module(..., source_filename=doc.source_filename, ...)` call therefore persisted the temp-file name (e.g. `tmpa_dwvrll.pdf`) into the `modules` table, which `module_library_page.py` then displays verbatim as "Source: tmpXXXXXX.pdf". Fixed by threading the original filename (`uploaded.name`, already cached in `st.session_state["_cached_upload_name"]` for the retry-with-same-file path) through `_start_pipeline` → `_run_pipeline_bg` as an explicit `original_filename` argument — required because the pipeline runs on a background thread that cannot reliably read `st.session_state` — and using it instead of `doc.source_filename` at the `save_module()` call site. `Document.source_filename` itself is otherwise unused outside that one call site, so no parser/model changes were needed. Verified by driving `_run_pipeline_bg` directly end-to-end against `tests/fixtures/sample.pdf` with `original_filename="Intro_to_ML_Lecture.pdf"` and confirming the saved row's `source_filename` matches the original name, not the temp path. **Note:** the 3 modules already in this user's local DB before the fix permanently lost their original filenames (never captured) and will continue to show their old `tmpXXXXXX.pdf` names — only new uploads are affected by the fix. Full pytest suite: 139 passed, 0 failures.
- [x] **Highlight each slide's "Key concepts" in different colors in the tutor room (Phase 64)** — **Resolved (enhancement):** `frontend/tutor_room.py::_render_slide()` previously rendered `top_concepts` as a single `st.info()` box with all concepts in identical backtick-styled text (`` `concept` | `concept` ``), giving no visual distinction between individual topics. Added `topic_highlight_chips_html()` to `frontend/styles.py` — renders each concept as its own colored pill, cycling through a fixed 6-color palette (blue/purple/teal/orange/pink/green, each a pastel background + matching dark text, same self-contained style as the existing `slide_chips_html`/`concept_rail_html` chips) — and swapped the `st.info()` call for a plain `st.markdown("**Key concepts:**")` label (inherits theme text color normally) followed by the chip row. Verified live in both themes via a synthetic harness: 6 distinct chip colors render correctly in light mode and remain identical (self-contained backgrounds, unaffected by theme CSS) in dark mode, with the label text correctly following the theme. Full pytest suite: 139 passed, 0 failures.
- [x] **"Top concepts" still shown as one undifferentiated blue box in the Module Viewer (Phase 65)** — **Resolved:** Phase 64 only fixed the live Adaptive Tutor's slide rendering (`frontend/tutor_room.py::_render_slide()`). The static Module Viewer page (shown when browsing a module's topics directly, outside a tutor session) has its own, separate "Top concepts" rendering in `frontend/module_viewer.py` — `st.info(f"Top concepts: {' | '.join(f'**{c}**' for c in et.top_concepts)}")` — which Phase 64 never touched, so it still wrapped every concept in one uniform `st.info()` box (Streamlit's info boxes render with a single blue-tinted background/text, which is exactly what made every concept look "all blue" regardless of content). Reported live with real content: "Self-Attention Mechanism", "Token Representation in Embedding Space", "Attention Weights" all rendering blue and pipe-separated. Fixed by applying the same `topic_highlight_chips_html()` treatment used in Phase 64: replaced the `st.info(...)` call with `st.markdown("**Top concepts:**")` + the chip row. Verified live with the exact 3 reported concept strings, in both light and dark mode — now rendering as 3 distinct chips (blue/purple/teal). Full pytest suite: 147 passed, 0 failures.
- [x] **Module Viewer: switching topic tabs doesn't stop the previous tab's audio; two tabs' audio can play simultaneously (Phase 66)** — **Resolved:** `frontend/module_viewer.py` renders each topic as an `st.tabs()` panel with its own `st.audio(et.audio_path, format="audio/mp3")` (no autoplay — user clicks play manually). Streamlit's `st.tabs()` keeps every tab panel (and its `<audio>` element) mounted in the DOM at all times, only hiding inactive ones via CSS — the same "all panels stay mounted" mechanic already documented as the root cause of the earlier Mermaid-in-tabs bug. Since nothing paused the previous tab's audio on switch, playing audio in tab 1 then clicking tab 2 left tab 1's audio running; playing tab 2's audio too then overlapped both. The existing fix for this exact class of bug, `frontend/audio_autostop.py::render_audio_autostop()` (Phase 54, built for the Adaptive Tutor — an invisible iframe whose script pauses every `<audio>` element on any `<button>` click), was wired into `tutor_room.py` but never into `module_viewer.py`. Confirmed live via Playwright DOM inspection that Streamlit's `st.tabs()` headers render as real `<button role="tab" data-testid="stTab">` elements, so the existing click selector (`e.target.closest('button')`) already covers tab switches with no changes needed to `audio_autostop.py` itself — the only gap was the missing call. Fixed by adding `render_audio_autostop()` to the top of `render_module_viewer()`, identical to the existing `tutor_room.py` pattern. Verified live with two real audio files across two tabs: starting tab 1's audio then clicking tab 2 paused tab 1's audio (confirmed via the audio element's `paused` property, not just visual hiding); starting tab 2's audio afterward left tab 1 still paused (no overlap); switching back to tab 1 likewise paused tab 2's audio. Full pytest suite: 147 passed, 0 failures.

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
