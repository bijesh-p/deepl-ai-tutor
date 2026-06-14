# CLAUDE.md — AI Tutor Project

## Project Overview

AI Tutor is a Streamlit web app that turns uploaded documents (PDF, PPTX, DOCX) into interactive learning modules. It decomposes content into sub-topics, generates diagrams, embeds inline questions, and provides end-of-module quizzes with difficulty selection and cohort analytics.

## Tech Stack

| Layer              | Technology                                              |
| ------------------ | ------------------------------------------------------- |
| Frontend           | Streamlit (Python)                                      |
| LLM abstraction    | `content/llm_client.py` — never import provider SDKs elsewhere |
| Database           | SQLite via `sqlite3` stdlib                             |
| Document parsing   | `PyMuPDF` (PDF), `python-pptx` (PPTX), `python-docx` (DOCX) |
| Diagram generation | Mermaid (LLM-generated code) + matplotlib               |
| Package manager    | `uv`                                                    |
| Python             | 3.14+                                                   |

## Setup

```bash
uv sync
cp .env.example .env   # fill in AI_TUTOR_LLM_API_KEY
streamlit run app.py
```

## Environment Variables

| Variable                | Default              | Notes                  |
| ----------------------- | -------------------- | ---------------------- |
| `AI_TUTOR_LLM_PROVIDER` | `openai`             |                        |
| `AI_TUTOR_LLM_API_KEY`  | (required)           | Never commit to source |
| `AI_TUTOR_LLM_MODEL`    | `gpt-4o`             |                        |
| `AI_TUTOR_DB_PATH`      | `data/ai_tutor.db`   |                        |
| `AI_TUTOR_UPLOAD_DIR`   | `data/uploads`       |                        |
| `AI_TUTOR_MAX_FILE_MB`  | `50`                 |                        |

## Directory Structure

```
course_project/
├── app.py                      # Streamlit entry point
├── ingestion/                  # Stream 1: parse PDF/PPTX/DOCX → Document
│   ├── models.py               # Document, Section, ExtractedImage dataclasses
│   ├── pdf_parser.py           # parse_pdf(file_path) -> Document
│   ├── pptx_parser.py          # parse_pptx(file_path) -> Document
│   ├── docx_parser.py          # parse_docx(file_path) -> Document
│   └── image_extractor.py      # extract_images(...) -> list[ExtractedImage]
├── content/                    # Stream 2: Document → LearningModule
│   ├── llm_client.py           # LLMClient — only place provider SDKs are imported
│   ├── topic_decomposer.py     # decompose(doc, llm) -> list[Topic]
│   ├── content_enricher.py     # enrich(topic, llm) -> EnrichedTopic
│   ├── diagram_generator.py    # generate_diagrams(topic, llm) -> list[Diagram]
│   └── inline_question_gen.py  # generate_inline_questions(topic, llm) -> list[Question]
├── quiz/                       # Stream 3: LearningModule → QuizResult
│   ├── question_bank.py        # generate_question_bank(module, llm) -> QuestionBank
│   ├── difficulty.py           # classify_difficulty(bank, llm) -> QuestionBank
│   ├── assembler.py            # assemble_quiz(bank, difficulty, n) -> Quiz (no LLM)
│   └── evaluator.py            # evaluate(quiz, user_answers) -> QuizResult
├── analytics/                  # Stream 4: persist results, compute stats
│   ├── db.py                   # get_db() -> sqlite3.Connection (auto-creates tables)
│   ├── persistence.py          # save_user / save_attempt / get_user_attempts / save_module
│   └── stats.py                # get_module_stats(module_id) -> ModuleStats
├── frontend/                   # Stream 5: Streamlit pages
│   ├── upload_page.py          # render_upload_page()
│   ├── module_viewer.py        # render_module_viewer(module)
│   ├── quiz_page.py            # render_quiz_page(bank)
│   └── results_page.py         # render_results_page(result, stats)
├── tests/
│   ├── test_ingestion/
│   ├── test_content/
│   ├── test_quiz/
│   ├── test_analytics/
│   └── fixtures/               # Sample PDF, PPTX, DOCX for testing
└── data/                       # Runtime — gitignored
    ├── uploads/
    ├── generated/
    └── ai_tutor.db
```

## Running Tests

```bash
uv run pytest
```

Analytics tests must use an **in-memory SQLite database** (`":memory:"`), not the file-based one.

## Architecture Rules

### LLM calls
- All LLM calls go through `LLMClient.generate(prompt, system, response_schema)` in `content/llm_client.py`.
- No module outside `content/llm_client.py` may import `openai`, `anthropic`, `google.generativeai`, or any other provider SDK directly.
- Retry once on LLM failure, then surface the error.
- Timeout per call: 60 seconds.
- Default token budget per module generation: 100,000 tokens (configurable).

### Data flow
```
Upload → Stream 1 (Document) → Stream 2 (LearningModule) → Stream 3 (QuizResult) → Stream 4 (ModuleStats)
                                                                          ↑
                                                              Stream 5 (Streamlit) wires everything
```

### Testing independently
Each stream can be developed and tested without the others:
- Streams 1: leaf — no dependencies.
- Stream 2: use `MockLLMClient` + hardcoded `Document` fixtures.
- Stream 3: use `MockLLMClient` + hardcoded `LearningModule` fixtures.
- Stream 4: create `QuizResult` fixtures directly; use `":memory:"` SQLite.
- Stream 5: use hardcoded mock objects for all dataclasses.

## Key Data Models (Quick Reference)

All authoritative definitions live in the module source files.

### `Document` (ingestion/models.py)
`Document` → `sections: list[Section]` → `images: list[ExtractedImage]`

`Section` fields: `section_id`, `title`, `body`, `level`, `images`, `metadata`  
`ExtractedImage` fields: `image_id`, `file_path`, `caption`, `source_location`

Parsers expose `to_json()` / `from_json()` on `Document`.

### `LearningModule` (content/models.py)
`LearningModule` → `topics: list[EnrichedTopic]`  
`EnrichedTopic` → `topic: Topic`, `content_html`, `key_takeaways`, `diagrams: list[Diagram]`, `inline_questions: list[Question]`

`Diagram.diagram_type`: `"mermaid"` or `"extracted_image"`  
`Question.question_type`: `"single_choice"` or `"multiple_choice"`

### `QuestionBank` / `Quiz` / `QuizResult` (quiz/models.py)
`QuizQuestion.difficulty`: `"easy"` | `"medium"` | `"hard"`  
`QuizResult` → `answers: list[AnswerResult]`

### `ModuleStats` (analytics/models.py)
Fields: `total_attempts`, `min_score`, `max_score`, `avg_score`, `user_score`, `user_percentile`, `user_attempts`

## SQLite Schema

```sql
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS modules (
    module_id TEXT PRIMARY KEY, title TEXT NOT NULL, source_filename TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS quiz_attempts (
    attempt_id TEXT PRIMARY KEY, quiz_id TEXT NOT NULL, module_id TEXT NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(user_id), difficulty TEXT NOT NULL,
    score INTEGER NOT NULL, total INTEGER NOT NULL, percentage REAL NOT NULL,
    completed_at TEXT NOT NULL, answers_json TEXT NOT NULL
);
```

Tables are auto-created by `get_db()` on first call.

## Non-Functional Constraints

- Max upload size: 50 MB; supported formats: `.pdf`, `.pptx`, `.docx` only.
- Document parsing target: < 30 s for a 50-page PDF.
- Module generation (LLM): 1-3 min — always show a progress indicator.
- Quiz assembly (no LLM): < 1 s.
- No API keys in source — always read from environment variables.

## Navigation Flow

Upload page → Module viewer → Quiz page → Results page → (Retake quiz | New upload)

Mermaid diagrams are stored as code strings; the frontend is responsible for rendering them.
