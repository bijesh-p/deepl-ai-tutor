# AI Tutor

A web application that transforms PDF documents into interactive, adaptive learning modules. Uses a direct LLM pipeline for content generation and a LangGraph state machine for personalised real-time adaptive tutoring.

## Project Status

- **Phase 1 (PDF POC):** ✅ Complete
- **Phase 2 (Functional Skeleton):** ✅ Complete — LLM factory, MCP tool servers, LangGraph adaptive tutor, JIT content pipeline, audio narration, ChromaDB vector store, and observability (Phoenix + DeepEval) are all implemented and tested.
- **Phase 3 (Refined Platform):** 🔄 In Progress — admin-curated module library ✅, full ChromaDB wiring into the tutor, PPTX/DOCX ingestion, live Portkey/Ollama end-to-end validation.

See [SPEC.md](SPEC.md) for the full phase breakdown and definitions of done.

## Features

- **PDF Ingestion** — Upload a PDF and extract structured content with heading-aware section splitting, via the `document_server` MCP tool (`extract_text_from_pdf`).
- **Multi-LLM Support** — Switch between Anthropic Claude, Portkey, or Ollama via sidebar or `.env`. All three adapters are covered by mocked unit tests (`tests/test_content/test_llm_client.py`); see `references.md` for the live Portkey/Ollama validation checklist.
- **Just-in-Time Content** — Upload and start learning within ~30 seconds. Topics are delivered as they are enriched; the rest generates in the background.
- **Personalised Adaptive Tutor** — LangGraph state machine (diagnostic quiz → depth-adapted slide → Q&A loop). Depth preference and topic mastery persist across sessions per username.
- **Diagram-Aware Audio** — Each topic slide includes TTS narration (edge-tts) that first describes the diagram, then explains the concept.
- **MCP Tool Servers** — Document parsing, assessment validation, and storage exposed as standalone MCP servers, dispatched via `backend/core/mcp_client.py`.
- **ChromaDB Vector Store** — Each enriched topic is upserted into ChromaDB (`all-MiniLM-L6-v2` embeddings) during generation via `storage_server.upsert_to_vector_db`, enabling semantic search over document chunks in `data/chroma/`.
- **Inline Questions** — Reinforcement questions embedded within each sub-topic for active learning.
- **Quizzes** — End-of-module quizzes with selectable difficulty, randomised questions, and explanations.
- **Performance Analytics** — Score tracking with cohort comparison (min/max/avg) across all participants.
- **LLM Observability** — OTEL traces sent to local Arize Phoenix; DeepEval quality metrics run after each session using the active LLM as judge. Toggle both on/off in the sidebar.
- **Admin Mode & Shared Library** — Usernames listed in `AI_TUTOR_ADMIN_USERNAMES` require `AI_TUTOR_ADMIN_PASSWORD` at login to become admins (sidebar shows "(Admin)"). Admins can publish/unpublish their own modules to a shared library (`data/shared/ai_tutor.db`), visible to every user in the Module Library's "Shared Library" section.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit (multi-page) |
| Content Generation | Direct LLM pipeline (decompose → enrich → diagrams → audio → quiz) |
| Adaptive Tutor | LangGraph (diagnostic + 5-node state machine) |
| LLM Providers | Anthropic SDK, Portkey, Ollama (OpenAI-compat) |
| Tool Protocol | MCP (Model Context Protocol) — 3 standalone servers |
| Vector Store | ChromaDB + sentence-transformers (`all-MiniLM-L6-v2`) |
| Database | SQLite |
| Document Parsing | PyMuPDF |
| Audio TTS | edge-tts (Microsoft Edge voices) |
| Diagrams | Mermaid (via `streamlit-mermaid`) |
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
uv sync

# 3. Configure environment — pick ONE provider below and edit .env

# 4. Run the app
PYTHONPATH=. uv run streamlit run app.py
```

Then open http://localhost:8501 in your browser.

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
PYTHONPATH=. uv run streamlit run app.py
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
| `AI_TUTOR_CHROMA_DIR` | — | ChromaDB storage directory | `data/chroma` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | — | Phoenix OTLP endpoint | `http://localhost:6006/v1/traces` |
| `LANGCHAIN_TRACING_V2` | — | Enable LangSmith tracing | — |
| `LANGCHAIN_API_KEY` | LangSmith | LangSmith API key | — |
| `LANGCHAIN_PROJECT` | LangSmith | LangSmith project name | `default` |

## Project Structure

```
course_project/
├── app.py                          # Streamlit entry point + sidebar
├── backend/
│   ├── core/
│   │   ├── llm_client/             # LLM factory + adapters (Anthropic, Portkey, Ollama)
│   │   └── mcp_client.py           # MCP tool dispatcher
│   ├── interactive_tutor/          # LangGraph state machine
│   ├── ingestion/                  # PDF parsing → Document model
│   ├── content/                    # Enricher, diagram generator, audio, questions
│   ├── quiz/                       # Question bank, assembly, scoring
│   ├── analytics/                  # SQLite persistence & cohort stats
│   └── observability/              # OTEL tracing setup + DeepEval runner
├── mcp_servers/
│   ├── document_server/            # extract_text_from_pdf, parse_images
│   ├── assessment_server/          # evaluate_taxonomy, validate_json_schema
│   └── storage_server/             # save_module_to_db, upsert/query_vector_db
├── frontend/
│   ├── upload_page.py              # PDF upload + content generation
│   ├── module_library_page.py      # Browse/select modules
│   ├── module_viewer.py            # Topic viewer + inline questions
│   ├── quiz_page.py                # Quiz with difficulty selector
│   ├── results_page.py             # Score + cohort analytics
│   └── tutor_room.py               # Adaptive tutor UI (LangGraph-driven)
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
