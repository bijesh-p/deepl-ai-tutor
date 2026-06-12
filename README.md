# AI Tutor

A web application that transforms PDF documents into interactive, adaptive learning modules. Uses CrewAI multi-agent pipelines for content generation and a LangGraph state machine for real-time adaptive tutoring.

## Features

- **PDF Ingestion** — Upload a PDF and extract structured content with heading-aware section splitting.
- **Multi-LLM Support** — Switch between Anthropic Claude, Portkey, or Ollama via environment config.
- **CrewAI Content Pipeline** — 3 sequential agents (Information Architect, Assessment Designer, Formatting Specialist) generate structured learning modules.
- **Classic Pipeline** — Direct LLM pipeline (decompose → enrich → diagrams → questions) also available.
- **Adaptive Tutor** — LangGraph state machine (5 nodes, conditional routing) adjusts difficulty, provides targeted hints, and simplifies concepts for struggling students.
- **MCP Tool Servers** — Document parsing, assessment validation, and storage exposed as standalone MCP servers.
- **ChromaDB Vector Store** — Semantic search over document chunks using `all-MiniLM-L6-v2` embeddings.
- **Inline Questions** — Reinforcement questions embedded within each sub-topic for active learning.
- **Quizzes** — End-of-module quizzes with selectable difficulty, randomized questions, and explanations.
- **Performance Analytics** — Score tracking with cohort comparison (min/max/avg) across all participants.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit (multi-page) |
| Content Generation | CrewAI (3 sequential agents) |
| Adaptive Tutor | LangGraph (5-node state machine) |
| LLM Providers | Anthropic SDK, Portkey, Ollama (OpenAI-compat) |
| Tool Protocol | MCP (Model Context Protocol) |
| Vector Store | ChromaDB + sentence-transformers (`all-MiniLM-L6-v2`) |
| Database | SQLite |
| Document Parsing | PyMuPDF |
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

# 3. Configure environment
cp .env .env.local
# Edit .env and set AI_TUTOR_LLM_API_KEY to your Anthropic API key

# 4. Run the app
PYTHONPATH=. uv run streamlit run app.py
```

Then open http://localhost:8501 in your browser.

## Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `AI_TUTOR_LLM_PROVIDER` | LLM provider: `anthropic`, `portkey`, or `ollama` | `anthropic` |
| `AI_TUTOR_LLM_API_KEY` | Anthropic API key (required for anthropic provider) | — |
| `AI_TUTOR_LLM_MODEL` | Model name | `claude-sonnet-4-6` |
| `AI_TUTOR_PORTKEY_API_KEY` | Portkey API key (for portkey provider) | — |
| `AI_TUTOR_PORTKEY_VIRTUAL_KEY` | Portkey virtual key (for portkey provider) | — |
| `AI_TUTOR_OLLAMA_BASE_URL` | Ollama endpoint | `http://localhost:11434/v1` |
| `AI_TUTOR_DB_PATH` | SQLite database path | `data/ai_tutor.db` |
| `AI_TUTOR_CHROMA_DIR` | ChromaDB storage directory | `data/chroma` |

## Project Structure

```
course_project/
├── app.py                          # Streamlit entry point
├── backend/
│   ├── core/
│   │   ├── llm_client/             # LLM factory + adapters (Anthropic, Portkey, Ollama)
│   │   └── mcp_client.py           # MCP tool dispatcher
│   ├── content_factory/            # CrewAI crew (3 sequential agents)
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
│   ├── upload_page.py              # PDF upload + pipeline selector
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
