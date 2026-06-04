# AI Tutor

A web application that transforms PDF documents into interactive learning modules with sub-topic decomposition, diagrams, inline questions, quizzes, and performance analytics.

> **Phase 1 POC** — PDF input, Anthropic Claude as LLM. PPTX/DOCX support coming in Phase 2.

## Features

- **PDF Ingestion** — Upload a PDF and extract structured content with heading-aware section splitting.
- **AI Content Generation** — Decomposes the document into focused sub-topics with enriched explanations, key takeaways, and Mermaid diagrams (powered by Anthropic Claude).
- **Inline Questions** — Reinforcement questions embedded within each sub-topic for active learning.
- **Quizzes** — End-of-module quizzes with selectable difficulty (easy/medium/hard), randomized questions, and detailed explanations.
- **Performance Analytics** — Score tracking with cohort comparison (min/max/avg) across all participants.

## Tech Stack

| Layer            | Technology                                       |
| ---------------- | ------------------------------------------------ |
| Frontend         | Streamlit                                        |
| LLM              | Anthropic Claude (`claude-sonnet-4-6`)           |
| Document Parsing | PyMuPDF                                          |
| Diagrams         | Mermaid (via `streamlit-mermaid`)                |
| Database         | SQLite                                           |
| Package Manager  | [uv](https://docs.astral.sh/uv/)                 |
| Python           | 3.14+                                            |

## Quick Start

```bash
# 1. Clone the repo
git clone <repo-url>
cd deepl-ai-tutor

# 2. Install dependencies (uv will create .venv automatically)
uv sync

# 3. Configure environment
cp .env.example .env
# Edit .env and set AI_TUTOR_LLM_API_KEY to your Anthropic API key

# 4. Run the app
uv run streamlit run app.py
```

Then open http://localhost:8501 in your browser.

## Environment Variables

Copy `.env.example` to `.env` and fill in your values.

| Variable                 | Purpose                    | Default               |
| ------------------------ | -------------------------- | --------------------- |
| `AI_TUTOR_LLM_PROVIDER`  | LLM provider name         | `anthropic`           |
| `AI_TUTOR_LLM_API_KEY`   | API key (required)        | —                     |
| `AI_TUTOR_LLM_MODEL`     | Model name                | `claude-sonnet-4-6`   |
| `AI_TUTOR_DB_PATH`       | SQLite database path      | `data/ai_tutor.db`    |
| `AI_TUTOR_UPLOAD_DIR`    | Upload directory          | `data/uploads`        |
| `AI_TUTOR_MAX_FILE_MB`   | Max upload size in MB     | `50`                  |

## Project Structure

```
deepl-ai-tutor/
├── app.py                  # Streamlit entry point
├── ingestion/              # PDF parsing → Document model
├── content/                # LLM pipeline: topics, enrichment, diagrams, questions
├── quiz/                   # Question bank generation, assembly, scoring
├── analytics/              # SQLite persistence & cohort stats
├── frontend/               # Streamlit UI pages (upload, learn, quiz, results)
├── tests/                  # Unit tests (25 tests, all passing)
│   └── fixtures/           # Sample PDF for tests
└── data/                   # Runtime data (gitignored)
    ├── uploads/
    ├── generated/
    └── ai_tutor.db
```

## Running Tests

```bash
uv run pytest tests/ -v
```

Expected: **25 passed**.

## Application Flow

```
Upload PDF
    │
    ▼
Parse Document ──▶ AI Pipeline ──▶ Quiz Engine
(PyMuPDF)          (decompose,      (question bank,
                    enrich,          assembly,
                    diagrams,        scoring)
                    questions)            │
                                         ▼
                   Streamlit UI ◀── Analytics
                 (learn → quiz      (SQLite,
                  → results)         min/max/avg)
```

## Architecture

See [SPEC.md](SPEC.md) for full specification, interface contracts, and work stream breakdown.
The implementation follows a spec-driven approach: all decisions are documented in SPEC.md before code is written.
