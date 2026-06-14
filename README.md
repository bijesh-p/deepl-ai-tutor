# AI Tutor

A web application that transforms PDF documents into interactive, adaptive learning modules. Uses a direct LLM pipeline for content generation and a LangGraph state machine for real-time adaptive tutoring.

## Features

- **PDF Ingestion** — Upload a PDF and extract structured content with heading-aware section splitting.
- **Multi-LLM Support** — Switch between Anthropic Claude, Portkey, or Ollama via environment config.
- **Just-in-Time Content** — Upload a PDF and start learning within ~30 seconds. Topics are delivered as they're enriched; remaining content generates in the background.
- **Adaptive Tutor** — LangGraph state machine (5 nodes, conditional routing) adjusts difficulty, provides targeted hints, and simplifies concepts for struggling students.
- **MCP Tool Servers** — Document parsing, assessment validation, and storage exposed as standalone MCP servers.
- **ChromaDB Vector Store** — Semantic search over document chunks using `all-MiniLM-L6-v2` embeddings.
- **Audio Narration** — Each topic includes a TTS audio player (edge-tts, Microsoft voices) so users can listen while reading.
- **Mandatory Diagrams** — Every topic gets a Mermaid concept map or flowchart showing how ideas relate.
- **Inline Questions** — Reinforcement questions embedded within each sub-topic for active learning.
- **Quizzes** — End-of-module quizzes with selectable difficulty, randomized questions, and explanations.
- **Performance Analytics** — Score tracking with cohort comparison (min/max/avg) across all participants.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit (multi-page) |
| Content Generation | Direct LLM pipeline (decompose → enrich → diagrams → quiz) |
| Adaptive Tutor | LangGraph (5-node state machine) |
| LLM Providers | Anthropic SDK, Portkey, Ollama (OpenAI-compat) |
| Tool Protocol | MCP (Model Context Protocol) |
| Vector Store | ChromaDB + sentence-transformers (`all-MiniLM-L6-v2`) |
| Database | SQLite |
| Document Parsing | PyMuPDF |
| Audio TTS | edge-tts (Microsoft Edge voices) |
| Diagrams | Mermaid (via `streamlit-mermaid`) |
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

Portkey acts as a gateway that routes requests to Google Vertex AI (which hosts Claude). This is the setup used in `api_check.py`. The Anthropic SDK talks to Portkey's endpoint, which forwards to Vertex AI — no direct Anthropic API key needed.

```bash
# .env
AI_TUTOR_LLM_PROVIDER=portkey
AI_TUTOR_LLM_MODEL=@vertexai-global/anthropic.claude-sonnet-4-6
PORTKEY_API_KEY=your-portkey-api-key       # from https://app.portkey.ai/
```

**How it works:** The adapter creates an Anthropic SDK client with `base_url=https://api.portkey.ai` and passes `PORTKEY_API_KEY` as a header. Portkey routes the request to whichever backend you configured in the Portkey dashboard (Vertex AI, direct Anthropic, Azure, etc.).

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

Use Anthropic's API directly with your own API key.

```bash
# .env
AI_TUTOR_LLM_PROVIDER=anthropic
AI_TUTOR_LLM_API_KEY=sk-ant-...            # from https://console.anthropic.com/
AI_TUTOR_LLM_MODEL=claude-sonnet-4-6
```

### Option C: Ollama (local, free)

Run models locally. No API key needed, but requires [Ollama](https://ollama.com/) installed.

```bash
# 1. Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 2. Pull a model (llama3.2 supports tool use; llama3 does NOT)
ollama pull llama3.2

# 3. Start the server (if not already running)
ollama serve

# 4. Configure .env
AI_TUTOR_LLM_PROVIDER=ollama
AI_TUTOR_LLM_MODEL=llama3.2
AI_TUTOR_OLLAMA_BASE_URL=http://localhost:11434/v1
```

**Important:** Use a model that supports **tool use / function calling** (e.g., `llama3.2`, `qwen2.5`). Models without tool support (e.g., `llama3`) will fail on structured output calls used by the content pipeline.

## Environment Variables

| Variable | Required for | Purpose | Default |
|---|---|---|---|
| `AI_TUTOR_LLM_PROVIDER` | All | LLM backend: `anthropic`, `portkey`, or `ollama` | `anthropic` |
| `AI_TUTOR_LLM_MODEL` | All | Model name | `claude-sonnet-4-6` |
| `AI_TUTOR_LLM_API_KEY` | `anthropic` | Anthropic API key | — |
| `PORTKEY_API_KEY` | `portkey` | Portkey API key | — |
| `AI_TUTOR_OLLAMA_BASE_URL` | `ollama` | Ollama endpoint | `http://localhost:11434/v1` |
| `AI_TUTOR_DB_PATH` | — | SQLite database path | `data/ai_tutor.db` |
| `AI_TUTOR_CHROMA_DIR` | — | ChromaDB storage directory | `data/chroma` |

## Project Structure

```
course_project/
├── app.py                          # Streamlit entry point
├── backend/
│   ├── core/
│   │   ├── llm_client/             # LLM factory + adapters (Anthropic, Portkey, Ollama)
│   │   └── mcp_client.py           # MCP tool dispatcher
│   ├── interactive_tutor/          # LangGraph state machine (5 nodes)
│   ├── ingestion/                  # PDF parsing → Document model
│   ├── content/                    # Models + classic LLM pipeline
│   ├── quiz/                       # Question bank, assembly, scoring
│   └── analytics/                  # SQLite persistence & cohort stats
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
│   ├── tutor_room.py               # Adaptive tutor chat UI
│   └── demo_mode.py                # Demo without LLM
├── tests/                          # 42 unit tests
├── SPEC.md                         # System specification
├── ARCHITECTURE.md                 # Architecture diagrams (Mermaid)
└── references.md                   # Technology references
```

## Running Tests

```bash
PYTHONPATH=. uv run pytest -v
```

Expected: **42 passed**.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed diagrams and [SPEC.md](SPEC.md) for the full specification.
