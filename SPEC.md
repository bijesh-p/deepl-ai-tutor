# SPEC.md — AI Tutor System Specification

> **Version:** 0.17 | **Last updated:** 2026-06-20
> Architecture, directory layout, and component design are in [ARCHITECTURE.md](ARCHITECTURE.md).

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
