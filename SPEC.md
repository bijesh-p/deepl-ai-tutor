# SPEC.md — AI Tutor System Specification

> **Version:** 0.31 | **Last updated:** 2026-06-23
> Architecture, directory layout, and component design are in [ARCHITECTURE.md](ARCHITECTURE.md).
> **GUI / frontend requirements are specified in [gui_spec.md](gui_spec.md)** — that document
> is authoritative for all GUI features, normative UI decisions (dark-theme default, button
> consistency), and suggested frontend improvements.

---

## 1. Release Status

| Phase | Name | Status | Key additions |
|-------|------|--------|---------------|
| 1 | PDF POC | ✅ Complete | Role-based access, Anthropic-only, SQLite, persistent module library |
| 2 | Functional Skeleton | ✅ Complete | LLM factory, MCP servers, LangGraph tutor, JIT pipeline, audio, observability |
| 3 | Refined Platform | 🔄 In Progress | Admin-curated module library, PPTX/DOCX, full ChromaDB wiring, dark mode, Bloom's-taxonomy quizzes, LLM guardrails |
| 4 | VTT Transcript Ingestion | ✅ Complete | Parse training/classroom `.vtt` transcripts into learning modules |

Remaining for Phase 3: live end-to-end validation against real Ollama/Portkey services (currently mocked-only — see `references.md`'s LLM Provider Validation checklist).

Detailed phase-by-phase implementation history (goals, files changed, fixes) lives in `plan.md`.

---

## 2. Non-Functional Requirements

### 2.1 File Constraints
- Max upload: 50 MB
- Supported formats: `.pdf`, `.pptx`, `.docx`, `.vtt`
- **Max topics per module:** Configurable via a numeric input on the upload page. When set to N > 0, the pipeline generates at most the N most important topics from the document. When 0 or blank, all topics are generated (default). Env-var default: `AI_TUTOR_DEFAULT_MAX_TOPICS` (default `0`). Applies to all document types uniformly.

### 2.2 LLM Usage
- All LLM calls go through `BaseLLMClient`, wrapped in `GuardrailedLLMClient` (§5) — no direct SDK imports outside `adapters/`
- Token budget per module generation: 200,000 tokens (configurable via `AI_TUTOR_TOKEN_BUDGET`)
- Timeout per call: 60 seconds; retry once on transient failure

### 2.3 Performance
- Time to first topic visible: ~20–40 seconds (parse + decompose + enrich 1 topic)
- Full module generation: 1–3 minutes total
- Quiz assembly (no LLM): < 1 s
- LangGraph node invocation: < 10 s per turn
- ChromaDB query: < 500 ms

### 2.4 Security
- No passwords for local development — username-only identification
- Admin identified by configured password (same as Phase 1 approach)
- API keys read from env; never logged or committed

---

## 3. Key Decisions Log

One line per decision — phase numbers point to `plan.md` for full implementation detail.

### Still Open

- [ ] **Portkey virtual key management** — one shared virtual key or per-user? Pending.

### Resolved

- **Content pipeline approach** — sliding-window decomposition + direct LLM calls with typed tool schemas.
- **Embedding model** (Phase 2) — local ONNX `all-MiniLM-L6-v2` via ChromaDB's `DefaultEmbeddingFunction` (no torch/`sentence-transformers`); fully offline.
- **LangGraph checkpointer** (Phase 33) — `tutor_room.py` invokes graph nodes manually, not via `.invoke()`, so a real `SqliteSaver` doesn't fit; session resume implemented instead via a custom `tutor_sessions` table.
- **PPTX/DOCX priority** — PDF only for Phase 2; PPTX/DOCX added in Phase 3 (Phase 35).
- **Hint generation strategy** — LLM-generated at runtime, grounded in the question, context, and the student's specific error.
- **Diagnostic quiz design** — 3 MCQ questions before the first slide; score sets `presentation_depth` (beginner/intermediate/advanced).
- **MCP client architecture** (Phase 29/30) — `backend/core/mcp_client.py` is a sync wrapper around the MCP SDK's stdio client; one subprocess per server, lazily-created singleton via `get_client(server_name)`.
- **document_server PDF parsing schema** (Phase 30) — `extract_text_from_pdf` delegates to `pdf_parser.parse_pdf`, returns `Document.to_json()`.
- **Portkey/Ollama Phase 2 validation scope** — mocked unit tests only (no live install available in-dev); manual live-validation checklist recorded in `references.md`.
- **Admin mode granularity** (Phase 32) — publish/unpublish own modules only, no edit/delete rights over others'; admin gated by `AI_TUTOR_ADMIN_USERNAMES` + `AI_TUTOR_ADMIN_PASSWORD`.
- **ChromaDB tutor-wiring scope** (Phase 34) — `provide_hint` always queries for grounding; `present_concept` only queries as a fallback when pipeline-enriched content isn't ready yet.
- **save_module_to_db MCP routing** (Phase 39) — routed through `mcp_client`, same delegation pattern as PDF parsing.
- **Per-topic mastery tracking** (Phase 33) — written incrementally to `topic_mastery` per concept, in addition to the end-of-session summary blob in `user_profiles`.
- **Mastery report page** (Phase 40) — standalone page, per-topic status + cohort comparison, viewable any time (not tied to quiz completion).
- **PPTX/DOCX parsing** (Phase 35) — dedicated parsers + MCP tools following the same pattern as PDF.
- **Observability dashboard** (Phase 37) — Phoenix link + DeepEval per-session table/chart, reachable from the sidebar and Module Library.
- **Dark mode persistence & theming mechanism** (Phase 41) — implemented via CSS injection (`frontend/styles.py`), since Streamlit's `[theme]` config is process-wide and can't be switched per-user at runtime; the preference persists via `user_profiles.dark_mode`.
- **Visual refresh color direction** (Phase 41) — kept the existing indigo/blue/purple brand identity, added one new teal accent + a matching dark palette.
- **Module viewer topic display** (Phase 41) — switched stacked always-expanded panels to `st.tabs()` for an always-visible topic index.
- **Sidebar couldn't be re-expanded once collapsed** (Phase 45-47) — a Streamlit 1.58.0 framework-level bug (confirmed in a vanilla app); fixed via a custom JS-forwarding button (`frontend/sidebar_toggle.py`).
- **Windows/Linux dependency compatibility** (Phase 46) — audited, no platform-specific risk found beyond the existing `onnxruntime` Intel-Mac pin.
- **Wrapping multiple Streamlit elements in one styled container** (Phase 48) — use `st.container(key=...)`, not two separate `st.markdown()` calls with an unclosed `<div>` (the latter doesn't nest).
- **VTT transcript ingestion** (Phase 4/41-45) — `vtt_parser.py` extracts teaching content and Q&A exchanges, strips speaker names for privacy; segmentation by topic shift, then time gap, then fixed-size chunking as a final fallback.
- **Merging `main` (VTT, e2e tests, robustness fixes) with `experiment/improve-ui` (dark mode, navigation)** (Phase 49) — merged `main` into `experiment/improve-ui`; the latter's per-user dark-mode toggle superseded `main`'s independently-grown forced-dark theme.
- **GUI overhaul: dark-theme default + button consistency** (Phase 56-57) — dark became the startup default; a per-user sidebar toggle lets each user switch to light, persisted to their profile; multi-button rows standardized to equal-width columns.
- **Quiz/diagnostic/tutor question difficulty model** (Phase 67-72) — replaced the ungrounded easy/medium/hard scale with Bloom's-taxonomy levels (remember/understand/apply/analyze/evaluate/create) across all four question-generation flows, informed by Scaria et al. (AIED 2024) — see `references.md`. Quizzes mix all six levels per attempt rather than picking one level.
- **Guardrails scope and architecture** (Phase 73-74) — see §5 below.

---

## 4. Resolved Issues Log

One line per fix. Both this log and `plan.md`'s "Bug Fixes" sections historically
referenced a `changes/` directory of standalone change specs that was never
committed to this repo — full root-cause detail for items without a `plan.md`
phase number lives only in the cited commit itself.

- **Mermaid diagrams could show raw mermaid.js syntax errors with no fallback** — replaced `streamlit-mermaid` with a custom vendored renderer + bullets fallback (`6d9cc4f`).
- **Hung/cyclic diagrams could render as a permanent blank box** — added a 5s client-side render timeout (`ac354a3`).
- **Diagrams broken for every Module Viewer topic except the first** — `st.tabs()` keeps inactive panels in a zero-size hidden DOM; deferred rendering until visible via `IntersectionObserver` (`e28544c`).
- **Adaptive Tutor could hang indefinitely between topics** — `storage_server`'s first MCP call pays a variable-cost `chromadb`/`numpy` import with no timeout; added a 30s call timeout + background pre-warm at startup (`766a8fb`).
- **Diagnostic quiz gave no feedback before the lesson started** — added a review screen (score + per-question breakdown) between the diagnostic and the first slide (`44505eb`, `b93a686`).
- **"Download Results" button white-on-white in dark mode** — native `st.download_button` wasn't covered by the existing `.stButton` dark-mode rule. See `plan.md` Phase 62.
- **Module Library showed the temp upload path instead of the original filename** — threaded the real filename explicitly through the background pipeline thread. See `plan.md` Phase 63.
- **Slide "Key concepts" / Module Viewer "Top concepts" were one undifferentiated blue box** — both replaced with color-coded chips. See `plan.md` Phases 64-65.
- **Module Viewer: switching topic tabs didn't stop the previous tab's audio** — wired the existing audio-autostop script into the module viewer too. See `plan.md` Phase 66.
- **Quiz "← Previous" button could crash with a negative progress value** — a rapid double-click could decrement the index past 0 before the disabled-state re-render landed; fixed by clamping the index instead of relying on an equality check. See `plan.md` Phase 52.
- **Mermaid diagrams missing for some Adaptive Tutor slides** — the diagram-validity check only checked truthiness (always true after sanitization); added real node/edge validation + a bullets fallback. See `plan.md` Phase 53.
- **`phoenix serve` failed to spawn** — the `arize-phoenix` package (which provides the CLI) had been accidentally dropped from dependencies during earlier debugging; restored. See `plan.md` Phase 55.

---

## 5. Guardrails — Input/Output Safety for LLM Calls

**Goal:** all 14 LLM call sites (interactive tutor nodes, content pipeline, quiz generation) went through `LLMFactory.create()` → `BaseLLMClient.generate()` with no input sanitization, no output moderation, and no scope control. Two surfaces carry genuinely untrusted content into prompts: uploaded document text and the student's raw free-text answer in the tutor room.

**Decisions:** four categories in scope — prompt-injection detection (input), content moderation (output), topic/scope relevance (input, tutor-room only), and a generic output-quality safety net (output). Architecture is a single decorator, `GuardrailedLLMClient`, wrapping `BaseLLMClient` and inserted at `LLMFactory.create()` — every call site is protected automatically with no per-call-site code. Violations block the call/output and raise `GuardrailViolation` with a friendly message (no silent sanitization, no log-only mode). Detection is hybrid: fast deterministic regex/keyword rules for injection and output-quality; an LLM-judge call for the two semantic checks, moderation and topic-relevance. Topic-relevance is wired only at `evaluate_response()` — the one tutor-room call site that embeds raw student text in its prompt.

Implemented in Phases 73-74 — see `plan.md` for the module layout (`backend/core/guardrails/`), call-site wiring, and test coverage.

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
| `AI_TUTOR_GUARDRAILS_ENABLED` | Master switch for all LLM guardrail checks (Phase 73) | `true` |
| `AI_TUTOR_GUARDRAILS_MODERATION_ENABLED` | Toggle the content-moderation judge check independently (Phase 73) | `true` |
| `AI_TUTOR_GUARDRAILS_TOPIC_RELEVANCE_ENABLED` | Toggle the topic-relevance judge check independently (Phase 73) | `true` |
| `PHOENIX_COLLECTOR_ENDPOINT` | Arize Phoenix OTEL endpoint | `http://localhost:6006/v1/traces` |
| `LANGCHAIN_API_KEY` | LangSmith API key (optional tracing) | — |
| `LANGCHAIN_TRACING_V2` | Enable LangSmith export | `false` |
