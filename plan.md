# plan.md — AI Tutor Implementation

> **Goal:** Deliver a fully working AI Tutor with adaptive tutoring, observability, and admin-curated module sharing.
> **Spec:** SPEC.md v0.25
> **Last updated:** 2026-06-22

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
- `frontend/tutor_room.py` — `_run_node` catches graph exceptions, stores `tutor_error` in session state, and calls `st.rerun()` to abort the button handler; new `_render_tutor_error` shows a user-readable message + technical expander + "Try again" / "Reset session" buttons

---

### Phase 37 — Observability dashboard ✅ Done

Dedicated page (`frontend/observability_page.py`) with two sections: (1) Phoenix trace explorer with `st.link_button` to open the Phoenix UI (base URL derived from `OTEL_EXPORTER_OTLP_ENDPOINT`); (2) DeepEval quality metrics — per-session table + avg score bar chart, queried via `get_eval_results()` in `backend/analytics/stats.py` (LEFT JOIN modules for module title). Navigation added to sidebar ("Observability" button) and module library home page ("📊 Observability" button in header row).

**Files:**
- `frontend/observability_page.py` (new) — Phoenix section + DeepEval section
- `backend/analytics/stats.py` — `get_eval_results(user_id, limit, db)` (note: placed in stats.py, not eval_runner.py, for consistency with other query functions)
- `app.py` — sidebar button + router case
- `frontend/module_library_page.py` — "📊 Observability" button in header

---

### Phase 38 — Test coverage ✅ Done

Integration tests for MCP servers, LLM factory adapters, and the LangGraph graph (dry-run with mock LLM responses). 119 tests pass (up from 88).

**Phase 38A — MCP server gaps:**
- `tests/test_mcp/test_assessment_server.py` (new) — `validate_json_schema`: valid schemas (learning_module, question, question_bank), missing keys, unknown schema name
- `tests/test_mcp/test_document_server.py` — added `extract_text_from_pptx` and `extract_text_from_docx` tests; fixtures generated inline via `tmp_path` using `python-pptx` / `python-docx`

**Phase 38B — LangGraph graph node tests:**
- `tests/test_tutor/test_graph_nodes.py` (new) — 17 tests covering all graph nodes: `generate_diagnostic` (questions populated, non-dict response), `evaluate_diagnostic` (all-correct/none-correct/partial/empty), `present_concept` (fast path with enriched+audio, fallback path via LLM), `ask_question`, `evaluate_response` (correct/incorrect/chat history), `simplify_foundations`, `_advance_concept` (next concept, empty remaining), `_session_complete`

**Phase 38C — Sliding pipeline tests:**
- `tests/test_content/test_sliding_pipeline.py` (new) — `_enrich_one` skip-on-error (Phase 36), success path, abort; `run_sliding_pipeline` returns topics, updates progress dict, skips failed topics and continues, aborts cleanly

---

### Phase 39 — MCPClient pipeline integration: save_module_to_db ✅ Done

`storage_server.save_module_to_db` gained an optional `db_path` param and now delegates to `backend.analytics.db.get_db(db_path)` + `backend.analytics.persistence.save_module(...)` (same delegation pattern as Phase 30's `extract_text_from_pdf` → `parse_pdf`), so the per-user DB's schema and migrations are applied. The dead `_get_db`/`_DB_PATH` helpers (previously raw `INSERT OR REPLACE` SQL against a fixed `AI_TUTOR_DB_PATH`) were removed. `frontend/upload_page.py`'s save-to-database step now calls `mcp_client.get_client("storage_server").call("save_module_to_db", ..., db_path=db_path)` instead of importing `persistence.save_module`/`db.get_db` directly.

**Files:**
- `mcp_servers/storage_server/server.py` — `save_module_to_db` delegates via `db_path` param; removed unused `_get_db`/`_DB_PATH`
- `frontend/upload_page.py` — save step routed through `mcp_client`; removed unused `save_module`/`get_db` imports
- `tests/test_mcp/test_storage_server_persistence.py` (new) — round-trips a module through the MCP tool and `persistence.load_module`

---

### Fix — onnxruntime/torch wheel unavailable on Intel macOS + Python 3.13

`uv sync` failed: `onnxruntime==1.26.0` (pulled in by `chromadb`) dropped `macosx_x86_64` wheels from 1.24.0 onward, and `torch` (pulled in transitively by `sentence-transformers`) has never shipped a `cp313`+`macosx_x86_64` wheel for any version — so this combination cannot be resolved on an Intel Mac running Python 3.13, regardless of pinning.

**Fix:**
- Pinned `onnxruntime<1.24` for `sys_platform == 'darwin' and platform_machine == 'x86_64'` in `pyproject.toml` (last version with Intel-Mac wheels is 1.23.2); other platforms keep resolving to the latest version `chromadb` requests.
- Replaced `SentenceTransformerEmbeddingFunction` with ChromaDB's built-in `DefaultEmbeddingFunction` (`mcp_servers/storage_server/server.py`) — an ONNX export of the same `all-MiniLM-L6-v2` model, run via `onnxruntime` instead of `sentence-transformers`/`torch`. This removes the `torch` dependency entirely (no version of which supports this platform/Python combo), and also drops ~20 transitive CUDA/`transformers` packages from `uv.lock`.
- Removed `sentence-transformers` from `pyproject.toml` dependencies (no longer used anywhere in the codebase).
- Deleted local `data/chroma/` (gitignored, regenerable dev data) since its collection metadata referenced the old `sentence_transformer` embedding function config and would otherwise fail to load with the new one.

**Files:** `pyproject.toml`, `uv.lock`, `mcp_servers/storage_server/server.py`, `SPEC.md`, `ARCHITECTURE.md`, `README.md`, `references.md`

---

## Phase 41 — UI/UX overhaul: dark mode color system + toggle 🔲 Planned

**Goal:** Add a per-user-persisted dark mode toggle. Since `.streamlit/config.toml` theming is process-wide and can't be switched per-user at runtime, dark mode is implemented entirely via the existing custom-CSS-injection mechanism in `frontend/styles.py`.

**Files:**
- `backend/analytics/db.py` — `_MIGRATIONS`: add `dark_mode INTEGER NOT NULL DEFAULT 0` column to `user_profiles`
- `backend/analytics/persistence.py` — `load_user_profile()` returns `dark_mode: bool`; new `save_dark_mode(user_id, dark_mode, db=None)` lightweight upsert (separate from the heavier `save_user_profile`)
- `frontend/login_page.py` — restore `st.session_state["dark_mode"]` from the loaded profile on login, alongside existing LLM-pref restore
- `frontend/styles.py` — light/dark palette tokens (app bg, card bg, text, sidebar gradient, borders); new teal accent `#14B8A6`; `_theme_overrides_css()` appended after the existing static `_GLOBAL_CSS`, gated on `st.session_state["dark_mode"]`
- `app.py` — `_render_sidebar()`: new "Dark mode" toggle alongside Audio/Tracing/Evals, persists via `save_dark_mode`

---

## Phase 42 — UI/UX overhaul: top-of-page back navigation ✅ Done

**Goal:** Every page gets a single, consistent back affordance at the top (not buried at the bottom), deduplicating the pattern already triplicated across pages.

**Files:**
- `frontend/nav.py` (new) — `render_back_button(label, target_page, key)`
- `mastery_report_page.py`, `observability_page.py`, `results_page.py` — move existing bottom back-button call to the top
- `quiz_page.py`, `module_viewer.py`, `upload_page.py`, `system_check_page.py` — add a back button (none exists today)
- `tutor_room.py` — back button routes through the existing end-session cleanup path, not a bare page-state swap

---

## Phase 43 — UI/UX overhaul: topic highlighting ✅ Done

**Goal:** Give the user a clear "where am I" indicator among topics — a concept rail in the adaptive tutor, and tabs (replacing stacked always-expanded expanders) in the early module view.

**Files:**
- `frontend/styles.py` — new `concept_rail_html(mastered, current, remaining)`, modeled on the existing `slide_chips_html()` pattern plus a new "pending" chip variant
- `frontend/tutor_room.py` — render the concept rail from `tutor_state["mastered_concepts"]`/`["current_concept"]`/`["remaining_concepts"]` (already in canonical module order)
- `frontend/module_viewer.py` — replace the per-topic `st.expander(expanded=True)` loop with `st.tabs()`

---

## Phase 44 — UI/UX overhaul: color/visual polish pass ✅ Done

**Goal:** Apply the new teal accent and refined contrast to the highest-impact surfaces; verify dark-mode contrast against this repo's own documented WCAG standard.

**Files:**
- `frontend/styles.py` — `score_banner_html()`, `page_header_html()`, `module_card_html()`, `concept_rail_html()` (from Phase 43)

---

## Phase 45 — Dark mode bug fixes: button contrast, purple re-theme, selector robustness ✅ Done

**Goal:** Fix three reported dark-mode problems: invisible secondary-button text at rest, sidebar collapse control reportedly unreachable, and re-theme the sidebar from indigo to purple.

**What shipped:**
- `.stButton button[kind="secondary"]` base (non-hover) dark rule added — secondary buttons only ever had a `:hover` color rule, so they fell back to Streamlit's light-theme text color (invisible on the new dark page) until hovered.
- **Root-caused a systemic selector bug**: every `.stButton > button` (direct-child) selector in the file silently stopped matching whenever Streamlit inserts an extra wrapper `<div>` inside `.stButton` — which happens for any button passing `help=`. Affected the sign-out button (in both light and dark mode, not just dark — a latent pre-existing bug) and would've affected any future `help=`-enabled button. Fixed by changing every occurrence to a descendant selector (`.stButton button`).
- Re-themed `_DARK_PALETTE`'s sidebar tokens (`sidebar_grad_start/end`, `sidebar_border`) and the `.sb-label` color from indigo/blue to violet, reusing the app's existing purple-accent family (`quiz_generating_html`, multi-choice badge). Contrast verified via computed WCAG ratios, not eyeballed.
- Fixed unselected `st.tabs()` text being invisible in dark mode (`_GLOBAL_CSS` only colored the *selected* tab).
- **Investigated but did not fix**: "can't re-expand a collapsed sidebar." Confirmed via a vanilla Streamlit app (same installed version, zero custom CSS) that this is a Streamlit 1.58.0 framework-level issue — `stSidebarCollapseButton` is `visibility:hidden` and never becomes reachable via hover anywhere along the page edge, with or without this app's CSS. Original hypothesis (a stale `stSidebarCollapsedControl` testid from an older Streamlit version, no longer present in 1.58.0) was correct in spirit but the testid simply doesn't exist anymore, so the original CSS targeting it (in both light and dark mode) was already dead code before this session. See `SPEC.md` Open Questions for the pending decision on how to proceed (live with it / custom JS workaround / Streamlit version bump).

**Files:**
- `frontend/styles.py` — `_theme_overrides_css()`, `_DARK_PALETTE`, and every `.stButton > button` occurrence throughout `_GLOBAL_CSS`

---

## Phase 46 — Streamlit upgrade check + Windows/Linux dependency audit ✅ Done

**Goal:** Follow up on Phase 45's open question — try a Streamlit version bump to fix the sidebar-collapse bug, and separately audit dependencies for Windows/Linux compatibility risk.

**Findings:**
- **No Streamlit upgrade is possible.** `pyproject.toml` already pins `streamlit>=1.58.0` (no ceiling); 1.58.0 (installed) is the current latest stable release (2026-05-28, confirmed via PyPI). Only `streamlit-nightly` (`1.58.1.dev20260616`) is newer — a pre-release dev build, not appropriate for this project.
- The sidebar-collapse bug is a recurring, not-version-specific class of issue in Streamlit's sidebar control (GitHub issues/forum reports going back to 1.25 and 1.38) — there's no specific fix version to wait for. The `collapsedControl` → `stSidebarCollapseButton` testid rename happened in 1.38; this app's CSS was still targeting the old name.
- Windows/Linux dependency audit: clean. Only `onnxruntime` has an active platform-specific pin (Intel-macOS-only; Windows/Linux unaffected). `pymupdf` has full prebuilt-wheel coverage across Windows/macOS/Linux (verified by reading `uv.lock` directly — `cp310-abi3` wheels cover Python 3.10 through 3.14 on regular builds). `sqlean-py` already has an automatic Windows/non-Windows split. No OS-specific code in this project's own source. Gap noted, not fixed: no CI/multi-platform test matrix exists.

**What shipped:**
- Removed the now-fully-confirmed-dead `stSidebarCollapsedControl` CSS block from `frontend/styles.py` (`_GLOBAL_CSS`, light mode) — verified via vanilla-Streamlit testing in Phase 45 that this testid no longer exists in 1.58.0's DOM.
- Updated the same stale testid reference in `frontend/login_page.py`'s defensive "hide sidebar on login page" guard to the correct current name, `stSidebarCollapseButton`.
- Updated comments explaining the sidebar's collapse behavior to reflect that it's now unstyled native Streamlit behavior, not a custom pull-tab.
- `SPEC.md` Open Questions updated to close out the version-bump option and document the dependency audit as resolved.

**Files:**
- `frontend/styles.py` — removed dead CSS block, updated comment
- `frontend/login_page.py` — corrected stale testid reference

---

## Phase 47 — Sidebar collapse/expand JS workaround ✅ Done

**Goal:** Resolve the Phase 45/46 open question — Streamlit's native sidebar collapse/expand control is unreachable via hover in this version, and no upstream fix exists to wait for. Build a custom JS-based workaround instead.

**Approach:** Streamlit's native control (`[data-testid="stSidebarCollapseButton"]`) is `visibility:hidden` by default, but calling `.click()` on it programmatically still triggers React's handler (confirmed in Phase 45's investigation) — only *mouse*-driven hover/click was blocked. So a custom always-visible button that forwards its click to the real control via JS sidesteps the bug entirely without touching Streamlit internals.

**What shipped:**
- New `frontend/sidebar_toggle.py::render_sidebar_toggle()` — renders a small floating button via `st.iframe()` (the non-deprecated successor to `st.components.v1.html`, which is being removed). The button's own `<script>` does `window.parent.document.querySelector('[data-testid="stSidebarCollapseButton"] button').click()` on click — works because the iframe is same-origin (served by the same Streamlit server).
- New `[data-testid="stIFrame"]` rule in `frontend/styles.py`'s `_GLOBAL_CSS` pins the iframe to a fixed 30×80px spot at the page's top-left edge, `z-index:999999`, so it floats above all content regardless of where in the script it's called.
- Button is theme-aware (violet gradient in dark mode, indigo/blue in light), matching the sidebar's own re-themed palette from Phase 45.
- Wired into `app.py`'s `main()`, called right after `_render_sidebar()`, inside the same `if st.session_state["page"] != "login"` guard — so it never renders on the login page (which has no sidebar).

**Verified live:** toggles the sidebar open and closed reliably via real Playwright clicks (not a JS-bypass test) in both light and dark mode; not present on the login page; zero browser console errors; `AppTest` smoke-clean in both theme states; full pytest suite unaffected (same 2 pre-existing unrelated failures).

**Files:**
- `frontend/sidebar_toggle.py` (new)
- `frontend/styles.py` — new `[data-testid="stIFrame"]` rule, updated sidebar comment block
- `app.py` — wired the call into `main()`

---

## Phase 48 — UI polish round 2: gray sidebar, quiz hover fix, login card fix ✅ Done

**Goal:** Three more reported UI bugs — sidebar should be gray not violet, quiz options become invisible on hover/select in dark mode, and the login page title renders outside its card.

**What shipped:**
- **Sidebar re-themed violet → slate-gray**: `_DARK_PALETTE`'s `sidebar_grad_start/end`/`sidebar_border` changed to slate-800/900/600 (`#1E293B`/`#0F172A`/`#475569`); `.sb-label` now reuses the existing `text_secondary` token instead of a hardcoded violet hex. `frontend/sidebar_toggle.py`'s button gradient updated to match (slate-600→800 resting, slate-500→700 hover).
- **Quiz option hover/checked invisible text, fixed**: root cause was that `_GLOBAL_CSS`'s `:hover` (`#F0F8FF`) and `:has(input:checked)` (`#EFF6FF`) backgrounds for radio/checkbox option cards are unconditional, near-white "light theme" colors — combined with the dark-mode base-state text color (`#F1F5F9`, also near-white), hovering or selecting an option produced near-white text on a near-white background. Added dark-mode-specific hover (`#233047` bg / `#60A5FA` border) and checked (`#1E3A5F` bg / `#3B82F6` border / `#BFDBFE` text) rules in `_theme_overrides_css()`.
- **Login page title-outside-card bug, fixed**: the card was built by opening a `<div class="login-canvas">` in one `st.markdown()` call and closing it in a separate, later call — Streamlit renders each call as an independent sibling, so nothing rendered in between (title, tabs, forms) actually nested inside the div; verified live that the closing tag left the title floating outside the white card. Replaced with `with st.container(key="login_canvas"):`, which Streamlit gives a real shared wrapper (class `st-key-login_canvas`) that every child genuinely nests inside. `_LOGIN_CSS` selectors updated from `.login-canvas` to `.st-key-login_canvas` to match.

**Verified live:** screenshotted hover/checked/checked+hovered quiz option states in dark mode (all legible); confirmed via DOM bounding-box containment check that the login title is now fully inside the card's rect; confirmed light mode is pixel-identical (no regression, all changes are dark-mode-gated or additive); `AppTest` clean on login + module_library in both themes; full pytest suite unaffected (same 2 pre-existing unrelated failures).

**Files:**
- `frontend/styles.py` — `_DARK_PALETTE` tokens, new quiz hover/checked dark rules
- `frontend/sidebar_toggle.py` — gray gradient colors
- `frontend/login_page.py` — `st.container(key=...)` restructure, `_LOGIN_CSS` selector updates

---

## Phase 4 — VTT Transcript Ingestion 🔲 Planned

> **Goal:** Parse WebVTT (`.vtt`) training/classroom transcripts into learning modules.
> Extract teaching content and Q&A, strip all speaker names (privacy), and plug into the
> existing enrichment pipeline so VTT uploads produce the same interactive experience as
> PDF/PPTX/DOCX.

### Phase 41 — SourceType enum + VTT parser core

**What:** Add `VTT` to the `SourceType` enum and implement `vtt_parser.py` with the full
parsing pipeline.

**Files:**
- `backend/ingestion/models.py` — add `VTT = "vtt"` to `SourceType`
- `backend/ingestion/vtt_parser.py` — **new file**, `parse_vtt(file_path, max_sections=16) -> Document`

**Parser internals (`parse_vtt`):**

1. **Read & validate** — Read file as UTF-8 (with BOM handling), verify `WEBVTT` header.
2. **Parse cues** — Extract each cue's start/end timestamps and text payload. Strip `NOTE`,
   `STYLE`, and `REGION` blocks.
3. **Speaker detection** — Detect speakers from `<v Name>text</v>` voice tags or
   `Speaker N: text` / `Name: text` line prefixes. Store speaker label per cue internally
   (used for turn detection and Q&A identification only — never exposed in output).
4. **Text cleanup** — Strip HTML tags (`<b>`, `<i>`, `<v>`, `<c>`, etc.), timestamps,
   cue IDs. Remove filler/chatter lines (greetings, logistics, "can you hear me?",
   "let me share my screen", etc.) using a pattern list. Collapse repeated whitespace.
5. **Q&A detection** — Identify question-answer pairs: lines ending with `?` or starting
   with question words ("what", "how", "why", "could you explain", etc.) followed by a
   different speaker's response. Tag these cue groups as Q&A.
6. **Segmentation** — Build sections using three-tier strategy:
   - **Topic shifts** — keyword signals ("let's move on to", "next topic", "now let's
     talk about") or sustained subject-matter change.
   - **Time gaps** — >30 s silence between consecutive cues → section boundary.
   - **Fixed chunks** — fallback: ~500-word boundaries → sections titled `"Part N"`.
7. **Q&A grouping** — Q&A cues are either:
   - Appended to the preceding topic section with a `---\n**Q&A**\n` separator, or
   - Collected into a dedicated `"Q&A: <inferred topic>"` section if they form a
     substantial standalone block.
8. **Section titling** — Titles are topic/concept labels, **never** speaker names.
   Format: `"Topic: <subject>"`, `"Q&A: <subject>"`, or `"Part N"` for fallback.
   Any speaker names remaining in body text are replaced with `"Instructor"` /
   `"Participant"`.
9. **Build Document** — Return `Document(source_type=SourceType.VTT, ...)` with max 16
   sections.

**Commit:** `[Phase 41] Add VTT parser with content extraction and Q&A capture`

---

### Phase 42 — MCP document_server tool

**What:** Expose `extract_text_from_vtt` in the MCP document server, following the
same pattern as PPTX/DOCX tools.

**Files:**
- `mcp_servers/document_server/server.py` — add `extract_text_from_vtt` tool

**Details:**
```python
@mcp.tool()
def extract_text_from_vtt(file_path: str, max_sections: int = 16) -> str:
    from backend.ingestion.vtt_parser import parse_vtt
    doc = parse_vtt(file_path, max_sections=max_sections)
    return doc.to_json()
```

**Commit:** `[Phase 42] Add extract_text_from_vtt MCP tool`

---

### Phase 43 — Upload page integration

**What:** Accept `.vtt` files in the upload page and route them through the pipeline.

**Files:**
- `frontend/upload_page.py` — add `.vtt` to `_TOOL_FOR_EXT`, file uploader `type` list,
  help text, and error messages

**Changes:**
1. `_TOOL_FOR_EXT[".vtt"] = "extract_text_from_vtt"`
2. `type=["pdf", "pptx", "docx", "vtt"]` in `st.file_uploader`
3. Update help text: `"PDF, PowerPoint, Word, or VTT transcript — up to ..."`
4. Update error message: `"Please upload a PDF, PPTX, DOCX, or VTT file."`

**Commit:** `[Phase 43] Add VTT to upload page file types`

---

### Phase 44 — Unit tests

**What:** Test the VTT parser (content extraction, Q&A detection, name stripping, edge
cases) and MCP round-trip.

**Files:**
- `tests/test_ingestion/test_vtt_parser.py` — **new file**
- `tests/test_mcp/test_document_server.py` — add VTT round-trip test
- `tests/fixtures/sample.vtt` — **new file**, test fixture with speaker turns + Q&A

**Test cases for `test_vtt_parser.py`:**

| Test | Verifies |
|---|---|
| `test_speaker_turns_produce_sections` | VTT with `<v>` tags → multiple sections, titled by topic not speaker |
| `test_no_speaker_names_in_output` | No speaker name appears in any `Section.title` or `Section.body` |
| `test_qa_extraction` | Question-answer exchanges are captured (either inline or as Q&A section) |
| `test_chatter_stripped` | Greetings, logistics, filler lines are not in output |
| `test_time_gap_segmentation` | VTT without speakers, >30s gaps → section boundaries |
| `test_fixed_chunk_fallback` | Long single-speaker transcript → ~500-word sections titled `"Part N"` |
| `test_single_cue` | Minimal VTT with one cue → one section |
| `test_empty_file` | VTT with only header → empty sections list |
| `test_max_sections_cap` | Large transcript respects `max_sections` limit |
| `test_source_type_is_vtt` | `doc.source_type == SourceType.VTT` |
| `test_document_roundtrip_json` | `Document.from_json(doc.to_json())` preserves all fields |

**MCP round-trip test in `test_document_server.py`:**

| Test | Verifies |
|---|---|
| `test_extract_text_from_vtt_matches_parse_vtt` | MCP tool returns same result as calling parser directly |

**Commit:** `[Phase 44] Add VTT parser and MCP round-trip tests`

---

### Phase 45 — README and references update

**What:** Update documentation to reflect VTT support.

**Files:**
- `README.md` — add VTT to features list, upload description, and file type references
- `references.md` — add WebVTT spec reference

**Commit:** `[Phase 45] Update docs for VTT transcript support`

---

### Phase 4 summary

| Phase | Scope | New files | Modified files |
|---|---|---|---|
| 41 | Parser + SourceType | `backend/ingestion/vtt_parser.py` | `backend/ingestion/models.py` |
| 42 | MCP tool | — | `mcp_servers/document_server/server.py` |
| 43 | Upload integration | — | `frontend/upload_page.py` |
| 44 | Tests + fixture | `tests/test_ingestion/test_vtt_parser.py`, `tests/fixtures/sample.vtt` | `tests/test_mcp/test_document_server.py` |
| 45 | Docs | — | `README.md`, `references.md` |

**Dependencies:** None — VTT is plain text parsed with Python stdlib (`re`, `pathlib`).

---

## Phase 49 — Merge `main` and `experiment/improve-ui` 🔲 Planned

**Goal:** Bring `experiment/improve-ui`'s UI/UX work (dark mode toggle, navigation, topic highlighting, sidebar fix) into `main` while keeping every functional feature `main` grew independently (VTT ingestion, provider e2e tests, diagram-sanitization robustness, adaptive-tutor session/navigation fixes, multi-format upload). Performed as `main` merged into `experiment/improve-ui` (not the reverse), so this branch can be reviewed before it lands on `main`.

**Why a manual merge was required:** both branches independently built a "dark theme" while diverging from the same ancestor (`871d377`). `main`'s version (`86728a5`) is a forced, permanent, process-wide dark theme (`.streamlit/config.toml` `base = "dark"` + a single hardcoded-dark `_GLOBAL_CSS`) with no toggle. `experiment/improve-ui`'s version is a proper per-user toggle (light default, dark on demand, persisted in `user_profiles.dark_mode`). These can't coexist, and `main`'s is superseded entirely.

**Resolution by file:**
- `frontend/styles.py`, `frontend/login_page.py` — kept `experiment/improve-ui`'s version wholesale. `main`'s changes here were exclusively the now-superseded forced-dark theme / an older login-card markup bug; no independent functional content to preserve.
- `.streamlit/config.toml` — reverted to its light-default values (auto-merge would have silently kept `main`'s forced-dark config, since `experiment/improve-ui` never touched this file — would have broken the toggle).
- `app.py` — kept `experiment/improve-ui`'s theme-aware sidebar text colors; manually removed `main`'s leftover "force sidebar permanently visible" CSS block, since it directly contradicts the working sidebar-toggle mechanism (`frontend/sidebar_toggle.py`) this branch built across Phases 45–47.
- `frontend/module_viewer.py` — true manual merge, not a side-pick: kept `main`'s `_sanitize_mermaid` + try/except diagram-crash guard, the top "🚀 Start Adaptive Tutor" button, and the sidebar "Contents" list (which also previews not-yet-generated topic titles during streaming — something the tabs view alone can't show), while adopting `experiment/improve-ui`'s `st.tabs()` topic navigation and top-of-page back button.
- `SPEC.md`, `plan.md` — combined both branches' phase history (no contradiction, both append-only).
- Everything else (`results_page.py`, `tutor_room.py`, `upload_page.py`, `backend/analytics/persistence.py`, `backend/analytics/db.py`, `README.md`) merged cleanly with both branches' features intact — verified by reading the actual merged blob content for each, not just trusting a clean auto-merge.

**Verified live:** full pytest suite passes (138 passed, 1 skipped, zero failures — the 2 previously-known pre-existing failures are also gone, fixed independently by `main`'s own commits); `AppTest` smoke-test clean; Playwright pass confirming login-card containment, dark-mode toggle (app bg switches to `#0F1117`), sidebar collapse/re-expand round-trip via the custom JS toggle, and `module_viewer.py` rendering tabs + back button + both action buttons + sidebar Contents list + a deliberately malformed diagram (to confirm the `_sanitize_mermaid`/try-except safety net survived the merge) without crashing.

**Files:** `app.py`, `.streamlit/config.toml`, `frontend/styles.py`, `frontend/login_page.py`, `frontend/module_viewer.py`, `SPEC.md`, `plan.md`, plus all cleanly auto-merged files above.

---

## Phase 50 — Fix invisible "Upload" button text in dark mode ✅ Complete

**Goal:** Fix `st.file_uploader`'s native "Browse files" button rendering white text on a white background in dark mode.

**Root cause:** this button (`data-testid="stBaseButton-secondary"`, `kind="secondary"`) is rendered directly inside `[data-testid="stFileUploader"]`, not wrapped in a `.stButton` div — so the existing `.stButton button[kind="secondary"]` dark-mode fix (Phase 45) never matched it. With no rule of its own, its text inherited `color: {text_primary}` (near-white) from the page-wide `.stApp` dark-mode rule (`frontend/styles.py:498`) while its background stayed Streamlit's native white.

**Fix:** added `[data-testid="stFileUploader"] button[kind="secondary"]` to `_theme_overrides_css()` in `frontend/styles.py`, using the same `card_bg`/`text_primary` tokens as every other secondary surface in dark mode.

**Verified live:** Playwright `getComputedStyle` check — light mode unchanged (`bg: #FFFFFF`, `color: #111827`); dark mode now `bg: #1A1D29`, `color: #F1F5F9`, contrast ratio 15.31:1 (WCAG AA requires 4.5:1). Full pytest suite unaffected (138 passed, 1 skipped, same as before).

**Files:** `frontend/styles.py` — one new CSS rule.

---

## Phase 51 — Restore missing `chromadb`/`deepeval` dependencies ✅ Complete

**Goal:** Fix `RuntimeError: upsert_to_vector_db failed: ... No module named 'chromadb'` surfaced in production logs from the content pipeline's `_store_in_vector_db` step.

**Root cause:** commit `ad72ea1` (on `main`'s lineage, pre-dating the Phase 49 merge) stripped `chromadb`, `deepeval`, `arize-phoenix`, and `sentence-transformers` from `pyproject.toml` during local debugging. Only `sentence-transformers` removal was intentional (already documented — replaced by ChromaDB's built-in ONNX embedding function). Since `experiment/improve-ui` never touched that dependency block, the Phase 49 merge silently inherited `main`'s deletion of the other three. `chromadb` is imported unguarded at module level in `mcp_servers/storage_server/server.py::_get_chroma_collection()`, so every vector-DB MCP call raised `ModuleNotFoundError` in production. `deepeval` has the same gap but is already guarded by a try/except in `backend/observability/eval_runner.py` (warns and no-ops). `arize-phoenix` has zero direct Python imports anywhere in the codebase (Phoenix runs as an external process, reached only via the already-present `opentelemetry-exporter-otlp-proto-http`) — correctly left out of the restore.

**Fix:** `uv add "chromadb>=1.5.9" "deepeval>=2.0.0"`, restoring the exact historical version constraints from before they were dropped.

**Verified live:** called the actual previously-failing `upsert_to_vector_db` and `query_vector_db` MCP tools end-to-end through `backend.core.mcp_client.get_client("storage_server")` — both now succeed. Full pytest suite unaffected (138 passed, 0 failures).

**Files:** `pyproject.toml`, `uv.lock`.

---

## Phase 52 — Fix negative quiz progress bar crash ✅ Complete

**Goal:** Fix `StreamlitAPIException: Progress Value has invalid value [0.0, 1.0]: -0.1` reported when clicking the quiz's "← Previous" button.

**Root cause:** `frontend/quiz_page.py`'s Prev/Next buttons used `disabled=(idx == 0)` / `disabled=is_last` (equality checks) while their click handlers did an unclamped `idx -= 1` / `idx += 1`. A rapid double-click sends two click events before the first rerun's disabled re-render reaches the browser: click 1 takes `idx` from `0` to `-1`; on the next render `disabled=(idx == 0)` is `False` (since `-1 != 0`), so the button renders enabled again and the queued second click decrements it to `-2`. With a 10-question quiz, `(idx + 1) / total_q = -1/10 = -0.1` — the exact reported value.

**Reproduced deterministically** via `AppTest`: forced `quiz_current_idx = -1` directly, confirmed the "← Previous" button rendered `disabled=False` (the bug), then clicked it to hit the exact `-0.1` exception.

**Fix:** both click handlers now clamp the new index into `[0, total_q - 1]` (`max(0, idx - 1)` / `min(total_q - 1, idx + 1)`), and both `disabled` checks use `<=`/`>=` instead of `==`. This also fixes a related latent bug — a negative `idx` would otherwise have silently wrapped to the wrong question via Python's negative list indexing instead of erroring.

**Verified:** re-ran the same `AppTest` repro against the fix — the button now renders correctly disabled at `idx <= 0`, and a forced click clamps to `0` instead of going negative. Full pytest suite unaffected (138 passed, 0 failures).

**Files:** `frontend/quiz_page.py`.

---

## Phase 53 — Fix missing Mermaid diagrams on some Adaptive Tutor slides ✅ Complete

**Goal:** Fix the report that some Adaptive Tutor slides show no Mermaid diagram.

**Root causes (two):**
1. `_sanitize_mermaid` always prepends a `flowchart TD` header to whatever it's given, so empty/garbage LLM output still comes back as a non-empty string (`"flowchart TD\n"`). `present_concept`'s two diagram-recovery paths in `backend/interactive_tutor/graph.py` only checked `if not mermaid_code:`, so this header-only string passed as "valid" and reached `st_mermaid()` as a diagram with no actual nodes — rendering blank or failing silently.
2. Neither recovery path had any fallback when no usable diagram resulted — unlike the main upload pipeline's `generate_slide_anchor`, documented to "hold either a Mermaid diagram or a bullet list — never both, never empty."

**Fix:**
- Extracted the node/edge validation `_try_diagram` already used (`_has_edge`, `_node_count`) into module-level functions plus a new `is_valid_mermaid()` in `backend/content/diagram_generator.py`, used both inside `_try_diagram` and at both `present_concept` call sites.
- Added the same bullets-fallback (`_try_bullets`, prepended into the transcript/content_md) to both `present_concept` paths whenever no valid diagram results, mirroring `generate_slide_anchor`'s guarantee.

**Verified:** added `test_present_concept_fallback_uses_bullets_when_no_diagram`; updated `test_present_concept_fallback_calls_llm`'s mock diagram to a real bracketed-node string since its old empty-string fixture now correctly triggers the bullets fallback instead of being accepted as valid. Full pytest suite: 139 passed, 0 failures.

**Files:** `backend/content/diagram_generator.py`, `backend/interactive_tutor/graph.py`, `tests/test_tutor/test_graph_nodes.py`.

---

## Phase 54 — Fix lingering slide audio + quiz results dark-mode contrast ✅ Complete

**Goal:** Fix three reported issues: (1) tutor slide audio keeps playing after switching slides/topics, (2) quiz results page "Question N" headers white-on-white in dark mode, (3) question text black-on-black in dark mode.

**Audio fix:** Streamlit reruns synchronously, so clicking "Next slide"/"Previous topic"/"Ask me a question" can involve several seconds of LLM/audio-generation work before the new page (without the old `st.audio` element) reaches the browser — the old audio keeps playing client-side the whole time. Confirmed via an isolated repro that `st.audio` itself correctly replaces/removes its DOM element across normal reruns (no leak there); the gap is purely the wait. Added `frontend/audio_autostop.py::render_audio_autostop()` — an invisible `st.iframe()` whose script adds a capture-phase click listener on `window.parent.document` that pauses any playing `<audio>` immediately on any button click. Called once at the top of `render_tutor_room()`.

**Dark-mode contrast fixes:**
- `[data-testid="stExpander"] summary` keeps Streamlit's native near-white background even when the outer expander gets a dark background — white text on that native background is white-on-white. Added `background: card_bg !important` to the summary selector in `_theme_overrides_css()`.
- `frontend/results_page.py`'s question-text div hardcoded `color:#111827` with no background of its own, sitting directly on the (dark, in dark mode) expander background. Replaced with a theme-aware `question_text_color`, same pattern as `app.py`'s `header_text_color`.

**Verified:** audio — live repro with autoplay forced on (`--autoplay-policy=no-user-gesture-required`) showed the audio paused within ~150ms of a button click, well before a simulated 2s backend delay finished. Contrast — synthetic results-page harness (fake `QuizResult`/`AnswerResult`, no real quiz needed) confirmed dark mode now shows white text on dark backgrounds for both the header and question text, light mode pixel-unchanged. Full pytest suite: 139 passed, 0 failures.

**Files:** `frontend/audio_autostop.py` (new), `frontend/tutor_room.py`, `frontend/styles.py`, `frontend/results_page.py`.

---

## Phase 55 — Fix missing `arize-phoenix` package breaking `phoenix serve` ✅ Complete

**Goal:** Fix `PYTHONPATH=. uv run phoenix serve` failing with `error: Failed to spawn: 'phoenix' — No such file or directory`.

**Root cause:** Phase 51 restored `chromadb`/`deepeval` after `main`'s lineage had stripped them from `pyproject.toml`, but explicitly left `arize-phoenix` out — reasoning it has zero direct Python imports in this codebase since Phoenix runs as a separate external process reached only via the already-present `opentelemetry-exporter-otlp-proto-http` exporter. That reasoning was incomplete: the README and `observability_page.py`'s own caption both document starting that external process via `PYTHONPATH=. uv run phoenix serve`, a CLI entry point that the `arize-phoenix` package itself provides (not the OTEL exporter packages). With the package absent from the `uv` venv, there was no `phoenix` console script for `uv run` to spawn.

**Fix:** `uv add arize-phoenix` (resolved to `arize-phoenix>=17.9.0`).

**Verified:** ran the exact documented command, polled `http://localhost:6006` until it returned `200` (first launch takes ~30s for Phoenix to run its internal Alembic DB migrations), confirmed the server log showed normal startup/migration output, then killed the process. Full pytest suite: 139 passed, 0 failures.

**Files:** `pyproject.toml`, `uv.lock`.

---

## Bug Fixes — Navaneeth

Compiled from standalone change plans scoped under `changes/` via the
`/spec-plan` skill before implementation (see each `changes/<name>.plan.md`
for full phase-by-phase detail, verification steps, and file lists).

### Mermaid diagram rendering reliability

**Phases:** A — vendor mermaid.js + `svg-pan-zoom` as static assets
(`frontend/static/vendor/`). B — build `frontend/mermaid_render.py`, an
`st.iframe()`-based custom renderer matching `streamlit-mermaid`'s
pan/zoom/controls UI. C — thread `key_takeaways` through `present_concept`'s
slide dict at both diagram-recovery paths. D — switch both call sites
(`tutor_room.py`, `module_viewer.py`) to the new renderer; remove the
`streamlit-mermaid` dependency.

**Verified:** existing `present_concept`/diagnostic tests pass; manual
walkthrough of valid and deliberately-broken diagrams in both the Adaptive
Tutor and Module Viewer, light and dark mode.

**Files:** see `SPEC.md` §3.

**Commit:** `[mermaid-render-reliability Phase D] Switch call sites off streamlit-mermaid, fix iframe CSS scoping` (`6d9cc4f`)

---

### Mermaid render timeout (hung diagrams)

**Phase 1:** race `mermaid.render()` against a 5s `setTimeout`; on timeout,
fall back identically to an error/rejection; a later-resolving render still
replaces the fallback with the real diagram.

**Verified:** isolated Node.js harness running the extracted IIFE against 4
controlled scenarios (success, error, hang-then-success, hang-then-fail).

**Commit:** `[mermaid-render-timeout Phase 1] Add render timeout fallback for hung diagrams` (`ac354a3`)

---

### Mermaid diagrams broken for every topic except the first

**Phase 1:** gate the renderer's first `mermaid.render()` call on an
`IntersectionObserver` confirming visibility; folded in (per a "clean diff"
request) removal of temporary debug logging and a revert of a
diagnostic-only `pan=False, zoom=False` toggle at both call sites.

**Verified:** isolated 4-tab Streamlit repro (tab 0 had the correct viewBox
before the fix, tabs 1-3 were broken; all 4 correct after); full pytest
suite green.

**Commit:** `[mermaid-render-visibility Phase 1] Defer mermaid.render() until content is visible` (`e28544c`)

---

### MCP client reliability: storage_server hang with no timeout

**Implemented directly** — no standalone change plan; root cause was dug
into via `py-spy` stack-trace dumping before deciding the fix (a timeout
alone, then a pre-warm added on top once the variable-cost import was
understood).

**What shipped:** 30s timeout on `MCPClient.call()`; `warm_up_storage_server()`
background pre-warm wired into `app.py` at startup.

**Verified:** dynamic tutor flow confirmed working live after a full process
restart (`app.py` + all MCP server subprocesses killed and relaunched).

**Commit:** `[mcp-client-reliability] Add call timeout and storage_server pre-warming` (`766a8fb`)

---

### Diagnostic quiz review screen

**Phase A:** add a required `explanation` field to `_DIAGNOSTIC_SCHEMA`/
`_DIAGNOSTIC_SYSTEM` in `graph.py`; update test fixtures.

**Phase B:** new `diagnostic_review` UI phase in `tutor_room.py` — the
submit handler now only evaluates the diagnostic and routes to the review
screen; new `_render_diagnostic_review()` (score + per-question breakdown)
with a "Continue to lesson →" button that runs the now-deferred
`present_concept`/slide transition.

**Phase C:** verification-only — `tutor_phase` is stored/restored as a plain
string with no fixed enum, so session-resume needed no code change for the
new phase.

**Verified:** unit tests for Phase A (`tests/test_tutor/test_graph_nodes.py`,
19 passed); manual walkthrough of the review screen for Phase B/C (no UI
test infra exists for `tutor_room.py`).

**Commits:** `[Phase A] Add explanation field to diagnostic questions` (`44505eb`), `[Phase B] Add diagnostic review screen before lesson slide` (`b93a686`)

---

## Bug Fixes — ported from `experiment/improve-ui`

## Phase 62 — Fix invisible "Download Results" button text in dark mode ✅ Complete

**Goal:** Fix `st.download_button("📥 Download Results", ...)` on the Quiz Results page rendering white text on a white background in dark mode.

**Root cause:** Same coverage gap as the Phase 50 upload-button fix, on a different native Streamlit element. `st.download_button()` renders inside `[data-testid="stDownloadButton"]`, not `.stButton`, so the existing `.stButton button[kind="secondary"]` dark-mode rule (`frontend/styles.py`) never matched it. With no dedicated rule, the button kept Streamlit's native white background while its text inherited the page-wide dark-mode `color: #F1F5F9` from `.stApp`.

**Fix:** added `[data-testid="stDownloadButton"] button[kind="secondary"]` to `_theme_overrides_css()` in `frontend/styles.py`, using the same `card_bg`/`text_primary` tokens as the Phase 50 file-uploader fix.

**Verified:** synthetic results-page harness (fake `QuizResult`/`AnswerResult`, no real quiz needed) — dark mode now resolves to `rgb(26,29,41)` background / `rgb(241,245,249)` text (was white-on-white); light mode confirmed pixel-unchanged (`rgb(255,255,255)` / `rgb(17,24,39)`). Full pytest suite: 139 passed, 0 failures.

**Files:** `frontend/styles.py`.

---

## Phase 63 — Save and display original uploaded filename, not the temp path ✅ Complete

**Goal:** Fix the Module Library showing uploaded documents as `tmpXXXXXX.pdf` instead of the original filename the user uploaded.

**Root cause:** `Document.source_filename` (set by every parser in `backend/ingestion/*_parser.py` as `path.name`) is derived from the `tempfile.NamedTemporaryFile` path the upload form writes the bytes to before parsing — the parsers never see the user's actual filename. `frontend/upload_page.py::_run_pipeline_bg` then persisted `doc.source_filename` (the temp name) into the `modules` table via `save_module()`, which `module_library_page.py` displays verbatim.

**Fix:** threaded the real filename (`uploaded.name`, already cached in `st.session_state["_cached_upload_name"]` for the "re-use last file" retry path) through `_start_pipeline` → `_run_pipeline_bg` as an explicit `original_filename` argument — needed because the pipeline runs on a background thread that can't reliably read `st.session_state` — and used it instead of `doc.source_filename` at the `save_module()` call site. `Document.source_filename` is otherwise unused, so no parser/model changes were needed.

**Verified:** drove `_run_pipeline_bg` directly against `tests/fixtures/sample.pdf` with `original_filename="Intro_to_ML_Lecture.pdf"` and confirmed the saved DB row's `source_filename` is the original name, not the temp path (`/var/folders/.../tmpo7h20rhl.pdf`). Full pytest suite: 139 passed, 0 failures. Note: 3 pre-existing modules in this user's local DB never captured their original filename and will keep showing `tmpXXXXXX.pdf` — only new uploads are fixed.

**Files:** `frontend/upload_page.py`.

---

## Phase 64 — Highlight each slide's "Key concepts" in different colors ✅ Complete

**Goal:** In the tutor room, make the "Key concepts" list at the top of each slide's explanation visually distinguish individual topics from each other, instead of one undifferentiated `st.info()` box.

**Change:** added `topic_highlight_chips_html()` to `frontend/styles.py` — renders each concept as its own colored pill, cycling through a fixed 6-color palette (blue/purple/teal/orange/pink/green), each chip self-contained with its own pastel background + matching dark text (same pattern as the existing `slide_chips_html`/`concept_rail_html` mastery chips, so it looks the same in light and dark mode without needing a theme check). `frontend/tutor_room.py::_render_slide()` now renders a plain `st.markdown("**Key concepts:**")` label followed by the chip row, instead of the old single-color `st.info()` box.

**Verified:** synthetic harness with 6 concepts — confirmed 6 visually distinct chip colors render correctly in both light and dark mode (chips unaffected by theme, as expected; label text correctly follows theme). Full pytest suite: 139 passed, 0 failures.

**Files:** `frontend/styles.py`, `frontend/tutor_room.py`.

---

## Phase 65 — Fix "Top concepts" still one undifferentiated blue box in Module Viewer ✅ Complete

**Goal:** Phase 64 fixed the Adaptive Tutor's per-slide "Key concepts" chips, but the user reported the same concepts still rendering "all blue" and pipe-separated when browsing a module directly.

**Root cause:** Phase 64 only touched `frontend/tutor_room.py::_render_slide()`. The Module Viewer page has its own separate, never-fixed "Top concepts" rendering — `frontend/module_viewer.py`: `st.info(f"Top concepts: {' | '.join(f'**{c}**' for c in et.top_concepts)}")` — Streamlit's `st.info()` box renders with one uniform blue-tinted background regardless of the content inside it, which is exactly the "all blue, pipe-separated" symptom reported (with real concepts: "Self-Attention Mechanism", "Token Representation in Embedding Space", "Attention Weights").

**Fix:** applied the same `topic_highlight_chips_html()` helper from Phase 64 here too — replaced the `st.info(...)` call with `st.markdown("**Top concepts:**")` + the chip row.

**Verified:** synthetic Module Viewer harness using the exact 3 concept strings from the bug report — confirmed 3 distinct chip colors (blue/purple/teal) in both light and dark mode. Full pytest suite: 147 passed, 0 failures.

**Files:** `frontend/module_viewer.py`.

---

## Phase 66 — Stop lingering audio when switching tabs in Module Viewer ✅ Complete

**Goal:** Fix the Module Viewer so switching topic tabs stops the previous tab's audio instead of letting it keep playing (and potentially overlap with the new tab's audio).

**Root cause:** Streamlit's `st.tabs()` keeps every tab panel — and its `st.audio()` element — mounted in the DOM at all times (only hiding inactive panels via CSS), the same mechanic already documented as the root cause of an earlier Mermaid-in-tabs bug. Nothing paused the previous tab's audio on tab switch. The existing reusable fix for this exact class of bug, `frontend/audio_autostop.py::render_audio_autostop()` (Phase 54, pauses every `<audio>` element on any `<button>` click), was wired into `tutor_room.py` but never into `module_viewer.py`.

**Investigated before fixing:** confirmed live via Playwright that Streamlit's tab headers render as real `<button role="tab" data-testid="stTab">` elements, so the existing click selector already covers tab switches — no change needed to `audio_autostop.py` itself, just the missing call site.

**Fix:** added `render_audio_autostop()` to the top of `render_module_viewer()`.

**Verified:** live test with two real audio files across two tabs — playing tab 1's audio then clicking tab 2 paused tab 1's audio (checked the element's `paused` property directly); starting tab 2's audio afterward showed no overlap; switching back to tab 1 paused tab 2's audio symmetrically. Full pytest suite: 147 passed, 0 failures.

**Files:** `frontend/module_viewer.py`.

---

## Phase 55 — Configurable Max Topics Limit ✅ Complete

**Goal:** Add a configurable "Slide count" slider on the upload page that caps how many topics/slides the pipeline generates. When set to N > 0, only the N most important topics are produced. When 0, all topics are generated (default). Useful for quick demos and targeted study.

**Changes:**
- `backend/content/sliding_pipeline.py` — `max_topics` param enforces cap in both sliding-window and VTT paths
- `frontend/upload_page.py` — slider UI, full pipeline progress view (no early redirect), completion summary, VTT parser dispatch fix, login redirect fix
- `app.py` — session persistence via query params, sign-out clears query params
- `frontend/login_page.py` — store username in query params on login
- `frontend/module_viewer.py` — remove sidebar "Contents" list
- `.env.copy`, `README.md`, `SPEC.md`, `plan.md` — docs

---

## Commit convention

Format: `[Phase N] <short description>`
Use the `/git-commit` skill after each phase — never run `git commit` directly.
