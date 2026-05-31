# AI Tutor

A web application that transforms static documents (PDF, PPTX, DOCX) into interactive learning modules with sub-topic decomposition, diagrams, inline questions, quizzes, and performance analytics.

## Features

- **Document Ingestion** — Upload PDF, PowerPoint, or Word files and extract structured content with images.
- **Content Generation** — LLM-powered decomposition into focused sub-topics with enriched explanations, key takeaways, and generated diagrams.
- **Inline Questions** — Reinforcement questions embedded within each sub-topic for active learning.
- **Quizzes** — End-of-module quizzes with selectable difficulty (easy/medium/hard), randomized questions, and detailed explanations.
- **Performance Analytics** — Score tracking with cohort comparison (min/max/avg) across all participants.

## Tech Stack

| Layer            | Technology                                          |
| ---------------- | --------------------------------------------------- |
| Frontend         | Streamlit                                           |
| LLM              | Configurable (OpenAI, Gemini, Anthropic, etc.)      |
| Document Parsing | PyMuPDF, python-pptx, python-docx                   |
| Database         | SQLite                                              |
| Package Manager  | [uv](https://docs.astral.sh/uv/)                    |
| Python           | 3.14+                                               |

## Project Structure

```
course_project/
├── app.py                  # Streamlit entry point
├── ingestion/              # Document parsing (PDF, PPTX, DOCX)
├── content/                # LLM-powered content & diagram generation
├── quiz/                   # Question bank, assembly, scoring
├── analytics/              # SQLite persistence & cohort stats
├── frontend/               # Streamlit UI pages
├── tests/                  # Unit tests + sample fixtures
└── data/                   # Runtime data (uploads, DB) — gitignored
```

## Setup

```bash
# Clone the repo
git clone <repo-url>
cd course_project

# Install dependencies
uv sync

# Set environment variables
export AI_TUTOR_LLM_PROVIDER=openai      # or gemini, anthropic
export AI_TUTOR_LLM_API_KEY=your-key
export AI_TUTOR_LLM_MODEL=gpt-4o         # or desired model

# Run the app
uv run streamlit run app.py
```

## Environment Variables

| Variable                 | Purpose                    | Default            |
| ------------------------ | -------------------------- | ------------------ |
| `AI_TUTOR_LLM_PROVIDER`  | LLM provider name         | `openai`           |
| `AI_TUTOR_LLM_API_KEY`   | API key for LLM provider  | (required)         |
| `AI_TUTOR_LLM_MODEL`     | Model name                | `gpt-4o`           |
| `AI_TUTOR_DB_PATH`       | SQLite database path      | `data/ai_tutor.db` |
| `AI_TUTOR_UPLOAD_DIR`    | Upload directory           | `data/uploads`     |
| `AI_TUTOR_MAX_FILE_MB`   | Max upload size in MB      | `50`               |

## Development

This project uses spec-driven development. See [SPEC.md](SPEC.md) for the full system specification, interface contracts, and work stream breakdown.

```bash
# Run tests
uv run pytest tests/

# Run a specific module's tests
uv run pytest tests/test_ingestion/
```

## Architecture

```
User uploads file
       │
       ▼
 Document Ingestion ──▶ Content Generation ──▶ Quiz Engine
  (PDF/PPTX/DOCX)        (LLM sub-topics,      (question bank,
                           diagrams, Q&A)        difficulty, scoring)
                                                       │
                                                       ▼
                          Streamlit UI  ◀────── Data & Analytics
                        (learn, quiz,            (SQLite, cohort
                         results)                 min/max/avg)
```
