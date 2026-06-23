# AI Tutor

A web application that transforms PDF documents into interactive, adaptive learning modules. Uses a direct LLM pipeline for content generation and a LangGraph state machine for personalised real-time adaptive tutoring.

## Project Status

- **Phase 1 (PDF POC):** ✅ Complete
- **Phase 2 (Functional Skeleton):** ✅ Complete — LLM factory, MCP tool servers, LangGraph adaptive tutor, JIT content pipeline, audio narration, ChromaDB vector store, and observability (Phoenix + DeepEval) are all implemented and tested.
- **Phase 3 (Refined Platform):** 🔄 In Progress — admin-curated module library ✅, ChromaDB wired into the LangGraph tutor ✅, PPTX/DOCX ingestion ✅, observability dashboard ✅, structured error messages + partial-failure recovery ✅, Bloom's-taxonomy quiz/diagnostic generation ✅, centralized LLM guardrails ✅, live Portkey/Ollama end-to-end validation.
- **Phase 4 (VTT Transcript Ingestion):** ✅ Complete — parse training/classroom `.vtt` transcripts into learning modules with teaching content extraction, Q&A capture, and speaker name privacy.

See [SPEC.md](SPEC.md) for the full phase breakdown and definitions of done.

## Features

- **Multi-Format Ingestion** — Upload a PDF, PowerPoint (`.pptx`), Word (`.docx`), or WebVTT transcript (`.vtt`). Each format has a dedicated parser (`pdf_parser`, `pptx_parser`, `docx_parser`, `vtt_parser`) exposed as an MCP tool via `document_server`, all producing the same `Document`/`Section` model consumed by the content pipeline. VTT transcripts from training recordings (Zoom, Teams, etc.) are parsed with teaching-content extraction, Q&A detection, chatter filtering, and speaker-name scrubbing (privacy).
- **Multi-LLM Support** — Switch between Anthropic Claude, Portkey, or Ollama via sidebar or `.env`. All three adapters are covered by mocked unit tests (`tests/test_content/test_llm_client.py`); see `references.md` for the live Portkey/Ollama validation checklist.
- **Centralized LLM Guardrails** — Every LLM call (all 14 call sites) passes through `GuardrailedLLMClient`, which the factory wraps around the real adapter automatically: prompt-injection detection and an output-quality safety net (fast regex/keyword checks), plus content-moderation and topic-relevance checks (LLM-judge) — the latter scoped to the one tutor-room call site that carries raw student free-text. Violations block with a friendly message rather than failing silently. Toggle via `AI_TUTOR_GUARDRAILS_ENABLED` (master switch) or the two judge-check-specific env vars below.
- **Just-in-Time Content** — Upload and start learning within ~30 seconds. Topics are delivered as they are enriched; the rest generates in the background.
- **Personalised Adaptive Tutor** — LangGraph state machine (diagnostic quiz → review → depth-adapted slide → Q&A loop). Depth preference and topic mastery persist across sessions per username. **Diagnostic review:** after submitting each topic's diagnostic quiz, a review screen shows the overall score plus a per-question breakdown (your answer, the correct answer, and a short explanation) before continuing into the lesson. **Session resume:** if a session ends before a module is finished, the tutor's full state (current concept, chat history, mastered topics) is saved to a `tutor_sessions` table and restored — with a "Resuming your previous session" banner and a "Restart from scratch" option — the next time that user opens the same module. Per-topic mastery (mastered/in-progress, difficulty, attempts) is also tracked incrementally in the `topic_mastery` table as each concept is completed.
- **Reliable Diagram Rendering** — Mermaid diagrams render through a custom client-side renderer (vendored mermaid.js + svg-pan-zoom, no CDN) instead of `streamlit-mermaid`, so a render failure can fall back to the topic's key-takeaway bullets instead of showing mermaid's raw syntax-error text. A 5-second client-side timeout catches diagrams whose layout engine hangs (e.g. cyclic graphs); diagrams inside an initially-hidden container (e.g. an inactive Module Viewer tab) defer rendering until they're actually visible, avoiding a Streamlit `st.tabs()` quirk that otherwise bakes in a broken near-zero-size layout.
- **Diagram-Aware Audio** — Each topic slide includes TTS narration (edge-tts) that first describes the diagram, then explains the concept.
- **MCP Tool Servers** — Document parsing, assessment validation, and storage exposed as standalone MCP servers, dispatched via `backend/core/mcp_client.py`. The content pipeline routes PDF parsing (`extract_text_from_pdf`), vector-store upserts (`upsert_to_vector_db`), and module persistence (`save_module_to_db`) through `mcp_client` rather than calling backend functions directly. Calls are bounded by a 30s timeout (`storage_server`'s first call pays a variable one-time `chromadb`/`numpy` import cost), and that import is pre-warmed in a background thread at app startup so a real user's first tutor session never pays it synchronously.
- **ChromaDB Vector Store** — Each enriched topic is upserted into ChromaDB (`all-MiniLM-L6-v2` embeddings) during generation via `storage_server.upsert_to_vector_db`, enabling semantic search over document chunks in `data/chroma/`. The LangGraph tutor queries this store via `storage_server.query_vector_db`: `provide_hint` grounds hints in retrieved chunks, and `present_concept` falls back to retrieved content when pipeline-enriched content isn't yet available in session state — both non-fatal on error.
- **Knowledge Graph (experimental)** — After a module's topics are enriched, an LLM extracts prerequisite/related/elaborates relationships between concepts into a per-module graph (`backend/content/knowledge_graph/`, NetworkX, persisted as GraphML under `data/graph/`). The tutor's `present_concept`/`provide_hint`/`simplify_foundations` nodes use it to pick which concepts to ground their context in (related concepts, prerequisites-first, or a prerequisite-ordered breakdown, respectively), pulling the actual definition text from ChromaDB — falling back to plain vector search whenever the graph is missing or doesn't help. `advance_concept` also reorders remaining topics by prerequisite order when a graph exists. Toggle the storage directory via `AI_TUTOR_GRAPH_DIR`.
- **Inline Questions** — Reinforcement questions embedded within each sub-topic for active learning.
- **Quizzes** — End-of-module quizzes mixing questions across all six Bloom's-taxonomy cognitive levels (remember / understand / apply / analyze / evaluate / create), each question tagged with its own level badge, randomised questions, and explanations.
- **Performance Analytics** — Score tracking with cohort comparison (min/max/avg) across all participants.
- **LLM Observability** — OTEL traces sent to local Arize Phoenix; DeepEval quality metrics (AnswerRelevancy, Faithfulness, ExplanationClarity) run after each tutor session using the active LLM as judge. Toggle both on/off in the sidebar. A dedicated **Observability Dashboard** page (reachable from the sidebar or the "📊 Observability" button on the Module Library) shows a Phoenix UI link and a per-session DeepEval results table with average score bar chart.
- **Admin Mode & Shared Library** — The login page has separate "User Login" and "Admin Login" tabs. User Login has no password (regular login, even for admin-listed usernames). Admin Login requires a username from `AI_TUTOR_ADMIN_USERNAMES` plus `AI_TUTOR_ADMIN_PASSWORD` (sidebar shows "(Admin)" on success). Admins can publish/unpublish their own modules to a shared library (`data/shared/ai_tutor.db`), visible to every user in the Module Library's "Shared Library" section.
- **Mastery Report** — Click "Mastery Report" on any module in the Module Library to see your per-topic progress (mastered / in progress / not started, difficulty reached, attempts) plus a cohort comparison showing the % of all users who have mastered each topic — viewable any time, not tied to quiz completion.
- **Configurable Max Topics** — A "Max topics" numeric input on the upload page lets you cap how many topics/slides the pipeline generates. Set to e.g. 5 for a quick demo with only the most important topics; leave at 0 (default) to generate all topics from the document. Works with all document types (PDF, PPTX, DOCX, VTT). Default value configurable via `AI_TUTOR_DEFAULT_MAX_TOPICS` env var.
- **Structured Error Handling & Partial Recovery** — Each pipeline step (parse, LLM connect, enrich, quiz, save) has its own error handler with a user-readable message and a collapsible technical details expander. If enrichment succeeds but quiz or save fails, a "Learn with N topic(s) →" button lets you jump straight into the tutor room with whatever was generated. A single bad topic during enrichment is silently skipped rather than killing the whole pipeline.
- **Dark Theme** — A "Dark mode" toggle in the sidebar lets each user switch between light and dark; the preference is saved per-user (`user_profiles.dark_mode`) and restored on the next login. Implemented via CSS injection in `frontend/styles.py` (no native Streamlit per-user theming support).
- **Reliable Sidebar Toggle** — Streamlit 1.58.0's native sidebar collapse/expand control is unreachable via hover (a framework-level issue, not specific to this app). `frontend/sidebar_toggle.py` adds a small always-visible custom button (top-left of the page) that forwards clicks to the hidden native control via JS — works reliably in both light and dark mode.
- **Consistent Back Navigation** — Every page (Upload, Module Viewer, Quiz, Results, Tutor Room, Mastery Report, Observability, System Check) has a single "← Back to Module Library" button at the top, via the shared `frontend/nav.py::render_back_button`. The Tutor Room's back button runs the same end-session cleanup as its "End Session" button so a session is never orphaned.
- **Topic Highlighting** — The Module Viewer shows topics as tabs (one click to jump between any topic, always-visible index) instead of stacked expanders. The Adaptive Tutor shows a concept rail above the slide — green ✓ chips for mastered concepts, a pulsing blue chip for the current one, and grey chips for what's still ahead — so you always know where you are in the module.
- **Visual Polish** — A new teal accent (`#14B8A6`) complements the existing blue/purple palette: a three-color gradient bar tops every page header banner, a "Perfect!" teal tier appears on the quiz results banner for scores ≥95%, and published/shared modules get a teal left-border in the Module Library to distinguish them from personal modules at a glance.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit (multi-page, single `app.py` router) |
| Content Generation | Direct LLM pipeline (decompose → enrich → diagrams → audio → quiz) |
| Adaptive Tutor | LangGraph (diagnostic + 8-node state machine) |
| LLM Providers | Anthropic SDK, Portkey, Ollama (OpenAI-compat) |
| Tool Protocol | MCP (Model Context Protocol) — 3 standalone servers |
| Vector Store | ChromaDB + ONNX `all-MiniLM-L6-v2` (via `onnxruntime`, no torch) |
| Database | SQLite — per-user DB + separate shared DB for published modules |
| Document Parsing | PyMuPDF (PDF), python-pptx, python-docx, WebVTT (stdlib) |
| Audio TTS | edge-tts (Microsoft Edge voices) |
| Diagrams | Mermaid (custom vendored renderer — `frontend/mermaid_render.py`) |
| Tracing | Arize Phoenix (local OTLP) + openinference auto-instrumentation |
| Eval Metrics | DeepEval (faithfulness, relevancy, clarity) |
| Package Manager | [uv](https://docs.astral.sh/uv/) |
| Python | 3.14+ |

## Quick Start

```bash
# 1. Clone the repo
git clone <repo-url>
cd course_project

# 2. Install dependencies (uv will create .venv automatically)
# This also installs Arize Phoenix (the `phoenix` CLI used for tracing below).
uv sync

# 3. Configure environment — pick ONE provider below and edit .env

# 4. Run the app
uv run python run.py
```

Then open http://localhost:8501 in your browser.

> **Note:** `run.py` sets `PYTHONPATH` automatically and launches Streamlit — no manual env-var prefix needed, works on both Linux/macOS and Windows.

> **Tracing:** to view LLM call traces, start the Phoenix server in a separate terminal — see [LLM Observability and Tracing](#llm-observability-and-tracing) below.

> **Upgrading from before the ONNX embedding switch?** If you already ran the app and have a local `data/chroma/` directory, delete it once after pulling (`rm -rf data/chroma`): its stored collection config points at the old `sentence-transformers` embedding function and will fail with `Could not build embedding function sentence_transformer` until removed. It's gitignored, local-only, and regenerates automatically on next use.

## LLM Provider Setup

The app supports three LLM backends. Set `AI_TUTOR_LLM_PROVIDER` in `.env` to switch between them. Only configure the variables for the provider you choose.

### Option A: Portkey → Vertex AI Claude (recommended for this project)

Portkey acts as a gateway that routes requests to Google Vertex AI (which hosts Claude). The Anthropic SDK talks to Portkey's endpoint, which forwards to Vertex AI — no direct Anthropic API key needed.

```bash
# .env
AI_TUTOR_LLM_PROVIDER=portkey
AI_TUTOR_LLM_MODEL=@vertexai-global/anthropic.claude-sonnet-4-6
PORTKEY_API_KEY=your-portkey-api-key       # from https://app.portkey.ai/
```

**Steps:**
1. Sign up at [app.portkey.ai](https://app.portkey.ai/)
2. Add a **Vertex AI** provider in the Portkey dashboard
3. Copy your Portkey API key into `.env` as `PORTKEY_API_KEY`
4. Model string format: `@vertexai-global/anthropic.<model-name>`

**Verify connectivity:**
```bash
PYTHONPATH=. uv run python api_check.py
```

### Option B: Anthropic (direct API)

```bash
# .env
AI_TUTOR_LLM_PROVIDER=anthropic
AI_TUTOR_LLM_API_KEY=sk-ant-...            # from https://console.anthropic.com/
AI_TUTOR_LLM_MODEL=claude-sonnet-4-6
```

### Option C: Ollama (local, free)

```bash
# 1. Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 2. Pull a model that supports tool use
ollama pull llama3.2

# 3. Start the server
ollama serve

# 4. Configure .env
AI_TUTOR_LLM_PROVIDER=ollama
AI_TUTOR_LLM_MODEL=llama3.2
AI_TUTOR_OLLAMA_BASE_URL=http://localhost:11434/v1
```

**Important:** Use a model that supports **tool use / function calling** (e.g., `llama3.2`, `qwen2.5`). Models without tool support will fail on structured output calls.

## LLM Observability and Tracing

AI Tutor instruments every LLM call with OpenTelemetry and sends traces to a local **Arize Phoenix** server — no account or internet access required.

### Seeing traces in Phoenix

```bash
# Terminal 1 — start Phoenix (keeps running while you use the app)
PYTHONPATH=. uv run phoenix serve

# Terminal 2 — start the AI Tutor app
uv run python run.py
```

Open **http://localhost:6006** to see the Phoenix trace UI. Every Anthropic SDK call, LangGraph node execution, and pipeline step (enrich / diagram / audio) appears as a named span.

### Enabling tracing and evals in the app

The sidebar has two toggles under **Observability**:

- **Tracing (Phoenix)** — on by default. Routes OTEL spans to Phoenix at `:6006`. Turn off if Phoenix is not running.
- **Evals (DeepEval)** — off by default (adds LLM calls after each session). Enable to run `AnswerRelevancy`, `Faithfulness`, and `ExplanationClarity` metrics. The **active provider/model** (e.g. Portkey → Claude) is used as the eval judge — no separate API key needed.

### Optional: LangSmith (cloud, secondary)

Add to `.env` to also send LangGraph traces to LangSmith:

```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls-...          # from https://smith.langchain.com/
LANGCHAIN_PROJECT=ai-tutor
```

No new package is required — LangGraph picks this up automatically.

## Environment Variables

| Variable | Required for | Purpose | Default |
|---|---|---|---|
| `AI_TUTOR_LLM_PROVIDER` | All | LLM backend: `anthropic`, `portkey`, or `ollama` | `anthropic` |
| `AI_TUTOR_LLM_MODEL` | All | Model name | `claude-sonnet-4-6` |
| `AI_TUTOR_LLM_API_KEY` | `anthropic` | Anthropic API key | — |
| `PORTKEY_API_KEY` | `portkey` | Portkey API key | — |
| `AI_TUTOR_OLLAMA_BASE_URL` | `ollama` | Ollama endpoint | `http://localhost:11434/v1` |
| `AI_TUTOR_DB_PATH` | — | SQLite database path | `data/ai_tutor.db` |
| `AI_TUTOR_DB_DIR` | — | Per-user DB directory (`<dir>/<username>/ai_tutor.db`) | `data` |
| `AI_TUTOR_SHARED_DB_PATH` | — | Shared DB for admin-published modules | `data/shared/ai_tutor.db` |
| `AI_TUTOR_ADMIN_USERNAMES` | Admin mode | Comma-separated admin usernames | — |
| `AI_TUTOR_ADMIN_PASSWORD` | Admin mode | Password required for admin usernames | — |
| `AI_TUTOR_DEFAULT_MAX_TOPICS` | — | Default "Max topics" value on upload page (0 = unlimited) | `0` |
| `AI_TUTOR_GUARDRAILS_ENABLED` | — | Master switch for all LLM guardrail checks | `true` |
| `AI_TUTOR_GUARDRAILS_MODERATION_ENABLED` | — | Toggle the content-moderation judge check independently | `true` |
| `AI_TUTOR_GUARDRAILS_TOPIC_RELEVANCE_ENABLED` | — | Toggle the topic-relevance judge check independently | `true` |
| `AI_TUTOR_CHROMA_DIR` | — | ChromaDB storage directory | `data/chroma` |
| `AI_TUTOR_GRAPH_DIR` | experiments/llm-graph | Per-module knowledge graph (GraphML) directory | `data/graph` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | — | Phoenix OTLP endpoint | `http://localhost:6006/v1/traces` |
| `LANGCHAIN_TRACING_V2` | — | Enable LangSmith tracing | — |
| `LANGCHAIN_API_KEY` | LangSmith | LangSmith API key | — |
| `LANGCHAIN_PROJECT` | LangSmith | LangSmith project name | `default` |

## Project Structure

```
course_project/
├── run.py                          # App runner — sets PYTHONPATH and launches Streamlit
├── app.py                          # Streamlit entry point, sidebar, page router
├── backend/
│   ├── core/
│   │   ├── llm_client/             # LLM factory + adapters (Anthropic, Portkey, Ollama)
│   │   ├── guardrails/             # GuardrailedLLMClient — input/output safety checks
│   │   └── mcp_client.py           # MCP tool dispatcher
│   ├── interactive_tutor/          # LangGraph state machine (graph.py)
│   ├── ingestion/                  # PDF/PPTX/DOCX/VTT parsing → Document model
│   ├── content/                    # Enricher, diagram generator, audio, questions, knowledge_graph/ (experimental)
│   ├── quiz/                       # Question bank, assembly, scoring
│   ├── analytics/                  # SQLite persistence, admin auth, cohort + mastery stats
│   └── observability/              # OTEL tracing setup + DeepEval runner
├── mcp_servers/
│   ├── document_server/            # extract_text_from_pdf/pptx/docx, parse_images
│   ├── assessment_server/          # evaluate_taxonomy, validate_json_schema
│   └── storage_server/             # save_module_to_db, upsert/query_vector_db
├── frontend/
│   ├── login_page.py               # User / Admin login tabs
│   ├── upload_page.py              # Upload + content generation, per-step error recovery
│   ├── module_library_page.py      # My Modules + Shared Library, admin publish controls
│   ├── module_viewer.py            # Topic viewer + inline questions
│   ├── quiz_page.py                # Quiz mixing all six Bloom's-taxonomy levels, per-question level badge
│   ├── results_page.py             # Score + cohort analytics
│   ├── tutor_room.py               # Adaptive tutor UI (LangGraph-driven), session resume
│   ├── mastery_report_page.py      # Per-topic + cohort mastery report
│   ├── observability_page.py       # Phoenix link + DeepEval metrics dashboard
│   └── system_check_page.py        # Env + package validation
├── tests/                          # Unit tests
├── SPEC.md                         # System specification
├── ARCHITECTURE.md                 # Architecture diagrams (Mermaid)
└── references.md                   # Technology references
```

## Running Tests

```bash
PYTHONPATH=. uv run pytest -v
```

Tests under `tests/test_mcp/` spawn the MCP servers as real subprocesses. `test_storage_server.py` is marked `slow` (it downloads the `all-MiniLM-L6-v2` embedding model on first run); skip it with:

```bash
PYTHONPATH=. uv run pytest -m "not slow"
```

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed diagrams and [SPEC.md](SPEC.md) for the full specification.
