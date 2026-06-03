# SPEC.md — AI Tutor System Specification

> **Version:** 0.3 (Role-based access + persistent module library)
> **Last updated:** 2026-06-03

---

## 0. Release Phases

The project is delivered in two phases to de-risk the LLM integration and end-to-end pipeline before broadening format support.

### Phase 1 — PDF POC (current)

**Goal:** A fully working, end-to-end application using **PDF as the only input format**. All five work streams must be functional and integrated. This phase proves the pipeline works and introduces role-based access with a persistent module library.

**Scope constraints:**
- Input: `.pdf` files only (PPTX and DOCX parsers are deferred to Phase 2)
- LLM provider: Anthropic Claude (via `anthropic` SDK) — single provider for POC
- Diagram type: Mermaid only (no extracted-image diagrams)
- Deployment: local Streamlit run (`streamlit run app.py`)
- **Two roles: Admin and User** (simple password for admin, username-only for users)
- PDF content capped at first 4 pages for POC to keep LLM calls fast

**Definition of done for Phase 1:**
- [ ] Admin logs in, uploads a PDF, and generates a learning module that is saved persistently
- [ ] Generated module and its question bank are stored in the database and reusable
- [ ] User logs in, browses the module library, selects a module, and works through it
- [ ] User can take a quiz at selectable difficulty and see their score
- [ ] Score is persisted; results page shows cohort min/max/avg comparison
- [ ] Full flow (Admin generates → User consumes) runs without errors

### Phase 2 — Full Format Support (future)

Adds PPTX and DOCX parsing, multi-provider LLM support, and extracted-image diagram rendering. Spec sections for these are already written below and serve as the future target.

---

## 1. System Overview

### 1.1 Problem

Static documents (PDFs, PowerPoint slides, Word docs) lead to passive learning and poor knowledge retention. Manually creating interactive learning content is expensive and hard to scale.

### 1.2 Solution

AI Tutor is a web application that transforms uploaded documents into interactive learning modules. It decomposes content into sub-topics, generates diagrams, embeds inline questions, and provides end-of-module quizzes with difficulty selection, randomization, and performance analytics.

The system operates with two distinct roles:

| Role | Responsibilities |
|------|-----------------|
| **Admin** | Logs in with a password, uploads PDFs, triggers AI module generation, publishes modules to the library |
| **User** | Logs in with a username, browses the module library, selects content to learn, takes quizzes, views their analytics |

Generated modules and their question banks are **persisted in the database** and reused for every subsequent learner — the LLM is only called once per document, at generation time by the admin.

---

### 1.3 User Flows

**Admin flow:**
```
Admin Login → Upload PDF → Generate Module (LLM pipeline) → Module saved to DB → Module appears in library
```

**User flow:**
```
User Login → Module Library → Select Module → Learn (topics + inline Qs) → Take Quiz → Results & Analytics
```

### 1.4 Tech Stack

| Layer              | Technology                                                         |
| ------------------ | ------------------------------------------------------------------ |
| Frontend           | Streamlit (Python)                                                 |
| Backend            | Python modules called directly from Streamlit                      |
| LLM                | Anthropic Claude (Phase 1); abstraction layer allows adding others |
| Database           | SQLite (via `sqlite3` stdlib)                                      |
| Document parsing   | `PyMuPDF` (PDF) — Phase 1 only; PPTX/DOCX added in Phase 2       |
| Diagram generation | Mermaid (via LLM-generated code)                                   |
| Package manager    | `uv`                                                               |
| Python version     | 3.14+                                                              |

### 1.5 High-Level Data Flow

```
┌─────────────┐     ┌──────────────────┐     ┌───────────────────┐
│  User        │     │  Stream 1:       │     │  Stream 2:        │
│  uploads     │────▶│  Document        │────▶│  Content          │
│  PDF         │     │  Ingestion       │     │  Generation       │
│  (Phase 1)   │     │  Pipeline        │     │  Engine           │
└─────────────┘     └──────────────────┘     └───────────────────┘
                                                      │
                                                      ▼
┌─────────────┐     ┌──────────────────┐     ┌───────────────────┐
│  Stream 5:   │◀───│  Stream 4:       │◀───│  Stream 3:        │
│  Frontend    │     │  Data &          │     │  Quiz             │
│  (Streamlit) │     │  Analytics       │     │  Engine           │
└─────────────┘     └──────────────────┘     └───────────────────┘
```

### 1.6 Project Directory Structure

```
course_project/
├── app.py                      # Streamlit entry point
├── SPEC.md
├── CLAUDE.md
├── pyproject.toml
├── README.md
├── references.md
│
├── ingestion/                  # Work Stream 1
│   ├── __init__.py
│   ├── pdf_parser.py
│   ├── pptx_parser.py
│   ├── docx_parser.py
│   ├── image_extractor.py
│   └── models.py               # Unified Document Model (dataclasses)
│
├── content/                    # Work Stream 2
│   ├── __init__.py
│   ├── llm_client.py           # LLM abstraction layer
│   ├── topic_decomposer.py
│   ├── content_enricher.py
│   ├── diagram_generator.py
│   └── inline_question_gen.py
│
├── quiz/                       # Work Stream 3
│   ├── __init__.py
│   ├── question_bank.py
│   ├── difficulty.py
│   ├── assembler.py
│   └── evaluator.py
│
├── analytics/                  # Work Stream 4
│   ├── __init__.py
│   ├── db.py                   # Schema + connection management
│   ├── persistence.py          # Save/load quiz results
│   └── stats.py                # Compute min/max/avg
│
├── frontend/                   # Work Stream 5
│   ├── __init__.py
│   ├── login_page.py           # Shared login: admin (password) or user (username)
│   ├── admin_upload_page.py    # Admin: upload PDF + trigger generation
│   ├── module_library_page.py  # User: browse and select published modules
│   ├── module_viewer.py        # User: read topics + answer inline questions
│   ├── quiz_page.py            # User: take quiz
│   └── results_page.py        # User: view score + cohort analytics
│
├── tests/                      # Mirrors the above structure
│   ├── test_ingestion/
│   ├── test_content/
│   ├── test_quiz/
│   ├── test_analytics/
│   └── fixtures/               # Sample PDF, PPTX, DOCX for testing
│
└── data/                       # Runtime data (gitignored)
    ├── uploads/                # Uploaded files
    ├── generated/              # Generated module JSON
    └── ai_tutor.db             # SQLite database
```

---

## 2. Work Stream 1: Document Ingestion Pipeline

### 2.1 Goal

Parse uploaded documents into a unified structured representation that downstream modules can consume without knowing the original file format.

**Phase 1 scope:** PDF only. The `Document` model and interface contract are defined for all formats so that adding PPTX/DOCX parsers in Phase 2 requires no changes downstream.

### 2.2 Subtasks

#### 2.2.1 PDF Parser (`ingestion/pdf_parser.py`)

- **Scope:** Extract text (preserving heading/paragraph structure), embedded images, and page boundaries from PDF files.
- **Library:** `PyMuPDF` (`fitz`)
- **Deliverable:** A function `parse_pdf(file_path: str) -> Document` that returns the unified model.
- **Notes:** Handle multi-column layouts on a best-effort basis. Extract images at their original resolution.

#### 2.2.2 PPTX Parser (`ingestion/pptx_parser.py`) — **Phase 2**

- **Scope:** Extract text from each slide (title + body), speaker notes, and embedded images/shapes.
- **Library:** `python-pptx`
- **Deliverable:** A function `parse_pptx(file_path: str) -> Document`.
- **Notes:** Each slide maps to one `Section` in the unified model. Speaker notes are included as metadata.

#### 2.2.3 DOCX Parser (`ingestion/docx_parser.py`) — **Phase 2**

- **Scope:** Extract text with heading hierarchy, paragraphs, lists, tables (as text), and embedded images.
- **Library:** `python-docx`
- **Deliverable:** A function `parse_docx(file_path: str) -> Document`.
- **Notes:** Use heading levels (H1-H6) to determine section boundaries.

#### 2.2.4 Image/Diagram Extractor (`ingestion/image_extractor.py`) — **Phase 2**

- **Scope:** Shared utility used by all three parsers to extract embedded images, save them to disk, and return file paths.
- **Deliverable:** A function `extract_images(source, output_dir: str) -> list[ExtractedImage]`.
- **Notes:** Images are saved as PNG. Each `ExtractedImage` has `path`, `caption` (if available), and `source_location` (page/slide number).

#### 2.2.5 Unified Document Model (`ingestion/models.py`)

- **Scope:** Define the common data structure that all parsers produce.
- **Deliverable:** Python dataclasses (see Interface Contract below).

### 2.3 Inputs

| Input           | Type       | Source     |
| --------------- | ---------- | ---------- |
| Uploaded file   | `bytes`    | User upload via Streamlit |
| File extension  | `str`      | Derived from filename     |

### 2.4 Outputs / Deliverables

A `Document` object (see §7.1 for full schema) containing:
- Document metadata (title, source filename, page/slide count)
- Ordered list of `Section` objects (heading + body text + images)
- Extracted images saved to `data/uploads/<doc_id>/images/`

### 2.5 Interface Contract

```python
# ingestion/models.py

from dataclasses import dataclass, field
from enum import Enum

class SourceType(Enum):
    PDF = "pdf"
    PPTX = "pptx"
    DOCX = "docx"

@dataclass
class ExtractedImage:
    image_id: str              # UUID
    file_path: str             # Path on disk (e.g., "data/uploads/<doc_id>/images/img_001.png")
    caption: str | None        # Extracted caption if available
    source_location: str       # "page 3" or "slide 5"

@dataclass
class Section:
    section_id: str            # UUID
    title: str                 # Heading text (or "Slide N" for PPTX without titles)
    body: str                  # Plain text content of the section
    level: int                 # Heading depth (1 = top-level)
    images: list[ExtractedImage] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)  # Speaker notes, table data, etc.

@dataclass
class Document:
    doc_id: str                # UUID
    title: str                 # Document title (from metadata or first heading)
    source_filename: str       # Original uploaded filename
    source_type: SourceType
    sections: list[Section]
    total_pages: int           # Page count (PDF) or slide count (PPTX) or section count (DOCX)
```

**Serialization:** The `Document` object can be serialized to/from JSON via `dataclasses.asdict()` + a custom deserializer. A `to_json()` / `from_json()` pair must be provided in `models.py`.

### 2.6 Acceptance Criteria

**Phase 1 (PDF only):**
- [ ] `parse_pdf` correctly extracts text and section structure from a 10-50 page PDF.
- [ ] `parse_pdf` produces a valid `Document` object consumable by Stream 2.
- [ ] Unit tests exist using a sample PDF fixture in `tests/fixtures/`.

**Phase 2 (deferred):**
- [ ] `parse_pptx` correctly extracts slide titles, body text, speaker notes, and images.
- [ ] `parse_docx` correctly extracts heading hierarchy and embedded images.
- [ ] All three parsers produce identical `Document` structure — downstream code cannot distinguish the source format.

### 2.7 Dependencies

None — this is a leaf work stream.

---

## 3. Work Stream 2: Content Generation Engine

### 3.1 Goal

Transform a parsed `Document` into an interactive learning module: decompose into sub-topics, enrich content for clarity, generate explanatory diagrams, and embed inline questions.

### 3.2 Subtasks

#### 3.2.1 LLM Abstraction Layer (`content/llm_client.py`)

- **Scope:** Provide a provider-agnostic interface for sending prompts and receiving structured responses from any LLM.
- **Deliverable:** A class `LLMClient` with method `generate(prompt: str, system: str | None, response_schema: dict | None) -> str | dict`.
- **Phase 1 provider:** Anthropic Claude (`anthropic` SDK). The abstraction layer is designed so additional providers (OpenAI, Gemini) can be added in Phase 2 without changing call sites.
- **Configuration:** Provider and API key read from environment variables (`AI_TUTOR_LLM_PROVIDER`, `AI_TUTOR_LLM_API_KEY`, `AI_TUTOR_LLM_MODEL`).
- **Notes:** All other subtasks in this stream (and Stream 3) call this client. They never import a provider SDK directly.

#### 3.2.2 Sub-topic Decomposer (`content/topic_decomposer.py`)

- **Scope:** Given a `Document`, use the LLM to break it into a logical sequence of learning sub-topics. Each sub-topic covers one focused concept.
- **Deliverable:** A function `decompose(doc: Document, llm: LLMClient) -> list[Topic]`.
- **Notes:** The LLM receives all section texts and returns a structured topic list. Each topic references which sections it draws from.

#### 3.2.3 Content Enricher (`content/content_enricher.py`)

- **Scope:** For each `Topic`, use the LLM to rewrite the content into clear, learner-friendly prose. Add analogies, key takeaways, and important definitions.
- **Deliverable:** A function `enrich(topic: Topic, llm: LLMClient) -> EnrichedTopic`.
- **Notes:** Preserve all factual content from the original document. The enrichment adds clarity, not new information.

#### 3.2.4 Diagram Generator (`content/diagram_generator.py`)

- **Scope:** For each topic, determine if a diagram would aid understanding. If so, generate Mermaid diagram code via the LLM. Also include any extracted images from the original document that are relevant to the topic.
- **Deliverable:** A function `generate_diagrams(topic: EnrichedTopic, llm: LLMClient) -> list[Diagram]`.
- **Notes:** Diagrams are stored as Mermaid code strings. The frontend renders them. Extracted images are referenced by path.

#### 3.2.5 Inline Question Generator (`content/inline_question_gen.py`)

- **Scope:** For each topic, generate 2-3 quick reinforcement questions (single-choice or multiple-choice) that test comprehension of that specific sub-topic.
- **Deliverable:** A function `generate_inline_questions(topic: EnrichedTopic, llm: LLMClient) -> list[Question]`.
- **Notes:** These are lightweight "check your understanding" questions, distinct from the comprehensive quiz in Stream 3.

### 3.3 Inputs

| Input       | Type       | Source        |
| ----------- | ---------- | ------------- |
| `Document`  | dataclass  | Stream 1 output |

### 3.4 Outputs / Deliverables

A `LearningModule` object (see §7.2) containing:
- Ordered list of `EnrichedTopic` objects
- Each topic has: enriched content, diagrams, inline questions
- Module metadata (title, source doc reference, topic count)

### 3.5 Interface Contract

```python
# content/models.py (or extend ingestion/models.py — team's choice)

@dataclass
class Topic:
    topic_id: str                    # UUID
    title: str
    summary: str                     # One-sentence summary
    source_section_ids: list[str]    # References to Section.section_id
    order: int                       # Position in the learning sequence

@dataclass
class Diagram:
    diagram_id: str
    diagram_type: str                # "mermaid" or "extracted_image"
    content: str                     # Mermaid code string, or file path for extracted images
    caption: str

@dataclass
class Question:
    question_id: str
    question_text: str
    question_type: str               # "single_choice" or "multiple_choice"
    options: list[str]               # 4 options
    correct_answers: list[int]       # Indices of correct option(s)
    explanation: str                 # Shown after answering

@dataclass
class EnrichedTopic:
    topic: Topic
    content_html: str                # Enriched content (Markdown or HTML)
    key_takeaways: list[str]
    diagrams: list[Diagram]
    inline_questions: list[Question]

@dataclass
class LearningModule:
    module_id: str                   # UUID
    title: str
    source_doc_id: str               # References Document.doc_id
    topics: list[EnrichedTopic]
    created_at: str                  # ISO 8601 timestamp
```

### 3.6 Acceptance Criteria

- [ ] `LLMClient` can be instantiated with at least one provider and returns structured responses.
- [ ] `decompose` breaks a 20-section document into 5-10 coherent topics.
- [ ] `enrich` produces readable prose that preserves original facts.
- [ ] `generate_diagrams` produces valid Mermaid syntax for at least 50% of topics.
- [ ] `generate_inline_questions` produces 2-3 questions per topic with correct answers.
- [ ] The full pipeline (`Document` → `LearningModule`) runs end-to-end with mock LLM responses in tests.

### 3.7 Dependencies

- **Stream 1:** Consumes the `Document` model.
- **For testing independently:** Use a `MockLLMClient` and hardcoded `Document` fixtures.

---

## 4. Work Stream 3: Quiz Engine

### 4.1 Goal

Generate comprehensive end-of-module quizzes with selectable difficulty, randomized question order, and automated scoring.

### 4.2 Subtasks

#### 4.2.1 Question Bank Generator (`quiz/question_bank.py`)

- **Scope:** Given a `LearningModule`, use the LLM to generate a large pool of questions (20-50) covering all topics. These are separate from the inline questions in Stream 2.
- **Deliverable:** A function `generate_question_bank(module: LearningModule, llm: LLMClient) -> QuestionBank`.
- **Notes:** Questions should cover different cognitive levels (recall, understanding, application).

#### 4.2.2 Difficulty Classifier (`quiz/difficulty.py`)

- **Scope:** Tag each question in the bank with a difficulty level: `easy`, `medium`, or `hard`. Can be done by the LLM during generation or as a post-processing step.
- **Deliverable:** A function `classify_difficulty(bank: QuestionBank, llm: LLMClient) -> QuestionBank` (mutates difficulty field).
- **Notes:** Alternatively, difficulty can be assigned during generation (in 4.2.1). The team should choose one approach.

#### 4.2.3 Quiz Assembler (`quiz/assembler.py`)

- **Scope:** Given a `QuestionBank` and a requested difficulty, select and randomize a fixed number of questions (e.g., 10) for a quiz session.
- **Deliverable:** A function `assemble_quiz(bank: QuestionBank, difficulty: str, num_questions: int = 10) -> Quiz`.
- **Notes:** No LLM needed — pure logic. Ensures no duplicate questions across consecutive attempts (best-effort).

#### 4.2.4 Quiz Evaluator (`quiz/evaluator.py`)

- **Scope:** Score user answers against correct answers. Compute per-question and total scores.
- **Deliverable:** A function `evaluate(quiz: Quiz, user_answers: dict[str, list[int]]) -> QuizResult`.
- **Notes:** `user_answers` maps `question_id` → list of selected option indices.

### 4.3 Inputs

| Input             | Type            | Source           |
| ----------------- | --------------- | ---------------- |
| `LearningModule`  | dataclass       | Stream 2 output  |
| `LLMClient`       | object          | Stream 2 (shared)|
| User's difficulty | `str`           | Frontend         |
| User's answers    | `dict`          | Frontend         |

### 4.4 Outputs / Deliverables

- `QuestionBank` — full pool of tagged questions
- `Quiz` — a single quiz session (subset of bank)
- `QuizResult` — scored result with per-question breakdown

### 4.5 Interface Contract

```python
# quiz/models.py

@dataclass
class QuizQuestion:
    question_id: str
    question_text: str
    question_type: str                # "single_choice" or "multiple_choice"
    options: list[str]
    correct_answers: list[int]
    explanation: str
    difficulty: str                   # "easy", "medium", "hard"
    topic_id: str                     # Which topic this tests

@dataclass
class QuestionBank:
    module_id: str
    questions: list[QuizQuestion]

@dataclass
class Quiz:
    quiz_id: str                      # UUID
    module_id: str
    difficulty: str
    questions: list[QuizQuestion]     # Ordered subset from bank
    created_at: str

@dataclass
class AnswerResult:
    question_id: str
    selected: list[int]
    correct: list[int]
    is_correct: bool
    explanation: str

@dataclass
class QuizResult:
    quiz_id: str
    module_id: str
    user_id: str
    score: int                        # Number correct
    total: int                        # Total questions
    percentage: float
    answers: list[AnswerResult]
    completed_at: str                 # ISO 8601
```

### 4.6 Acceptance Criteria

- [ ] `generate_question_bank` produces 20+ questions spanning all topics in a module.
- [ ] All questions have a valid difficulty tag.
- [ ] `assemble_quiz` returns exactly `num_questions` questions of the requested difficulty (falling back to adjacent difficulties if insufficient).
- [ ] `evaluate` correctly scores all question types.
- [ ] Consecutive quiz assemblies for the same module produce different question orderings.

### 4.7 Dependencies

- **Stream 2:** Consumes `LearningModule` and `LLMClient`.
- **For testing independently:** Use hardcoded `LearningModule` fixtures and `MockLLMClient`.

---

## 5. Work Stream 4: Data & Analytics Layer

### 5.1 Goal

Persist quiz results in a SQLite database and compute performance analytics (user score vs. cohort min/max/average) across all participants.

### 5.2 Subtasks

#### 5.2.1 Database Schema (`analytics/db.py`)

- **Scope:** Define and auto-create the SQLite schema. Provide connection management.
- **Deliverable:** A function `get_db() -> sqlite3.Connection` that creates tables on first call.
- **Schema:**

```sql
CREATE TABLE IF NOT EXISTS users (
    user_id    TEXT PRIMARY KEY,
    username   TEXT NOT NULL UNIQUE,
    role       TEXT NOT NULL DEFAULT 'user',   -- 'admin' or 'user'
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Stores the full LearningModule JSON so it can be reloaded without re-running the LLM.
-- Also stores the QuestionBank JSON for quiz reuse.
CREATE TABLE IF NOT EXISTS modules (
    module_id          TEXT PRIMARY KEY,
    title              TEXT NOT NULL,
    source_filename    TEXT NOT NULL,
    module_json        TEXT NOT NULL,   -- JSON-serialised LearningModule
    question_bank_json TEXT NOT NULL,   -- JSON-serialised QuestionBank
    created_by         TEXT NOT NULL REFERENCES users(user_id),
    created_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS quiz_attempts (
    attempt_id   TEXT PRIMARY KEY,
    quiz_id      TEXT NOT NULL,
    module_id    TEXT NOT NULL REFERENCES modules(module_id),
    user_id      TEXT NOT NULL REFERENCES users(user_id),
    difficulty   TEXT NOT NULL,
    score        INTEGER NOT NULL,
    total        INTEGER NOT NULL,
    percentage   REAL NOT NULL,
    completed_at TEXT NOT NULL,
    answers_json TEXT NOT NULL   -- JSON blob of list[AnswerResult]
);
```

#### 5.2.2 Score Persistence API (`analytics/persistence.py`)

- **Scope:** Functions to save quiz results and user records to the database.
- **Deliverable:**
  - `save_user(user_id: str, username: str) -> None`
  - `save_attempt(result: QuizResult) -> None`
  - `get_user_attempts(user_id: str, module_id: str) -> list[dict]`
  - `save_module(module: LearningModule) -> None`

#### 5.2.3 Analytics Computer (`analytics/stats.py`)

- **Scope:** Compute aggregate statistics for a module.
- **Deliverable:**
  - `get_module_stats(module_id: str) -> ModuleStats`
  - Returns min, max, average scores, total attempts, and the requesting user's percentile.

### 5.3 Inputs

| Input          | Type          | Source          |
| -------------- | ------------- | --------------- |
| `QuizResult`   | dataclass     | Stream 3 output |
| `user_id`      | `str`         | Frontend (session) |
| `module_id`    | `str`         | From LearningModule |

### 5.4 Outputs / Deliverables

```python
# analytics/models.py

@dataclass
class ModuleStats:
    module_id: str
    total_attempts: int
    min_score: float          # Minimum percentage across all attempts
    max_score: float          # Maximum percentage
    avg_score: float          # Average percentage
    user_score: float         # This user's latest percentage
    user_percentile: float    # Percentile rank (0-100)
    user_attempts: int        # How many times this user attempted
```

### 5.5 Acceptance Criteria

- [ ] Database tables auto-create on first run.
- [ ] `save_attempt` persists a `QuizResult` and `get_module_stats` returns correct aggregates.
- [ ] With 5+ attempts from different users, min/max/avg/percentile are computed correctly.
- [ ] Database file lives at `data/ai_tutor.db` (configurable via env var).
- [ ] Unit tests use an in-memory SQLite database.

### 5.6 Dependencies

- **Stream 3:** Consumes `QuizResult`.
- **For testing independently:** Create `QuizResult` fixtures directly — no dependency on Streams 1-2.

---

## 6. Work Stream 5: Frontend (Streamlit UI)

### 6.1 Goal

Build a role-aware Streamlit application. Admins generate and publish learning modules; users browse the module library, learn, and take quizzes. The LLM pipeline runs only once per document (at admin generation time); all subsequent learner sessions load from the database.

### 6.2 Authentication Model (Phase 1)

- **Admin:** Single admin account. Credentials stored in environment variables (`AI_TUTOR_ADMIN_USERNAME`, `AI_TUTOR_ADMIN_PASSWORD`). On successful login, `st.session_state["role"] = "admin"`.
- **User:** Any other username. No password required for Phase 1. On login, `st.session_state["role"] = "user"`.
- Session state keys: `role`, `user_id`, `username`.

### 6.3 Page Inventory

| Page | File | Who sees it | Purpose |
|------|------|-------------|---------|
| Login | `frontend/login_page.py` | Everyone | Enter username; admins also enter password |
| Admin Upload | `frontend/admin_upload_page.py` | Admin only | Upload PDF, run generation pipeline, save module |
| Module Library | `frontend/module_library_page.py` | Admin + User | Browse all published modules; select one to learn |
| Module Viewer | `frontend/module_viewer.py` | User | Read topics, inline questions |
| Quiz | `frontend/quiz_page.py` | User | Take end-of-module quiz |
| Results | `frontend/results_page.py` | User | Score + cohort analytics |

### 6.4 Subtasks

#### 6.4.1 Login Page (`frontend/login_page.py`)

- **Deliverable:** `render_login_page()`
- **UI elements:**
  - Username text input
  - Password text input (shown only when username matches `AI_TUTOR_ADMIN_USERNAME`, or always shown with a "Login as admin" toggle)
  - "Enter" button
- **Behaviour:**
  - If username == `AI_TUTOR_ADMIN_USERNAME` and password matches `AI_TUTOR_ADMIN_PASSWORD` → set `role=admin`, navigate to `admin_upload`
  - Otherwise → set `role=user`, navigate to `module_library`

#### 6.4.2 Admin Upload Page (`frontend/admin_upload_page.py`)

- **Deliverable:** `render_admin_upload_page()`
- **UI elements:**
  - PDF file uploader
  - "Generate Learning Module" button (disabled until file selected)
  - Live `st.status()` log showing all 6 pipeline steps
- **Behaviour:**
  - Runs the full pipeline: parse → decompose → enrich → diagrams → inline questions → question bank
  - Saves full `LearningModule` JSON and `QuestionBank` JSON to `modules` table
  - On success: shows confirmation with module title and link to module library

#### 6.4.3 Module Library Page (`frontend/module_library_page.py`)

- **Deliverable:** `render_module_library_page()`
- **UI elements:**
  - Searchable list / table of all saved modules (title, source file, date created)
  - "Learn" button per module → navigates to module viewer
  - Admin additionally sees a "Delete" button per module
- **Behaviour:**
  - Loads module list from `modules` table (title + created_at; no LLM call)
  - On "Learn": loads full `LearningModule` from `module_json` column, sets `st.session_state["module"]` and `st.session_state["bank"]`, navigates to `learn`

#### 6.4.4 Module Viewer (`frontend/module_viewer.py`) — unchanged from Phase 1

- **Deliverable:** `render_module_viewer(module: LearningModule)`
- Sidebar TOC, per-topic collapsible sections, Mermaid diagrams, inline questions with immediate feedback, "Take Quiz" button.

#### 6.4.5 Quiz Page (`frontend/quiz_page.py`) — unchanged from Phase 1

- **Deliverable:** `render_quiz_page(bank: QuestionBank)`
- Difficulty selector, question form, submit → evaluate → navigate to results.

#### 6.4.6 Results Page (`frontend/results_page.py`) — unchanged from Phase 1

- **Deliverable:** `render_results_page(result: QuizResult)`
- Score display, cohort bar chart, per-question breakdown, "Retake" and "Back to Library" buttons.

### 6.5 Navigation State Machine

```
[login]
   │
   ├─ role=admin ──▶ [admin_upload] ──▶ [module_library]
   │
   └─ role=user  ──▶ [module_library]
                          │
                          ▼
                      [learn]  ──▶  [quiz]  ──▶  [results]
                          ▲                          │
                          └──── "Back to Library" ───┘
```

### 6.6 Inputs

| Input                | Type            | Source     |
| -------------------- | --------------- | ---------- |
| Credentials          | `str`           | Login form |
| Uploaded PDF         | `UploadedFile`  | Admin upload page |
| `LearningModule`     | dataclass       | Loaded from DB `module_json` |
| `QuestionBank`       | dataclass       | Loaded from DB `question_bank_json` |
| `QuizResult`         | dataclass       | Stream 3 evaluator |

### 6.7 Acceptance Criteria

- [ ] Admin can log in with correct password; rejected on wrong password.
- [ ] Non-admin users reach the module library directly after entering a username.
- [ ] Admin generates a module; it immediately appears in the module library.
- [ ] User selects a module from the library and loads it without any LLM call.
- [ ] Full user flow works: Library → Learn → Quiz → Results → Back to Library.
- [ ] "Retake Quiz" produces a different question order.
- [ ] Application runs with `streamlit run app.py`.

### 6.8 Dependencies

- **All streams:** The frontend integrates outputs from Streams 1-4.
- **Stream 4 (persistence):** `save_module` must store `module_json`; `load_module` must deserialise it back to a `LearningModule` dataclass.

---

## 7. Interface Contracts Summary

This section collects all data models in one place for quick reference. The authoritative definitions live in the code modules listed in each work stream.

### 7.1 Document Model (Stream 1 → Stream 2)

```
Document
  ├── doc_id: str
  ├── title: str
  ├── source_filename: str
  ├── source_type: SourceType (pdf | pptx | docx)
  ├── total_pages: int
  └── sections: list[Section]
        ├── section_id: str
        ├── title: str
        ├── body: str
        ├── level: int
        ├── images: list[ExtractedImage]
        │     ├── image_id: str
        │     ├── file_path: str
        │     ├── caption: str | None
        │     └── source_location: str
        └── metadata: dict
```

### 7.2 Learning Module (Stream 2 → Streams 3, 5)

```
LearningModule
  ├── module_id: str
  ├── title: str
  ├── source_doc_id: str
  ├── created_at: str
  └── topics: list[EnrichedTopic]
        ├── topic: Topic
        │     ├── topic_id, title, summary, order
        │     └── source_section_ids: list[str]
        ├── content_html: str
        ├── key_takeaways: list[str]
        ├── diagrams: list[Diagram]
        │     ├── diagram_id, diagram_type, content, caption
        └── inline_questions: list[Question]
              ├── question_id, question_text, question_type
              ├── options: list[str]
              ├── correct_answers: list[int]
              └── explanation: str
```

### 7.3 Quiz Model (Stream 3 → Streams 4, 5)

```
QuestionBank
  ├── module_id: str
  └── questions: list[QuizQuestion]
        ├── question_id, question_text, question_type
        ├── options, correct_answers, explanation
        ├── difficulty: str (easy | medium | hard)
        └── topic_id: str

Quiz
  ├── quiz_id, module_id, difficulty, created_at
  └── questions: list[QuizQuestion]

QuizResult
  ├── quiz_id, module_id, user_id
  ├── score, total, percentage, completed_at
  └── answers: list[AnswerResult]
        ├── question_id, selected, correct
        ├── is_correct: bool
        └── explanation: str
```

### 7.4 Analytics Model (Stream 4 → Stream 5)

```
ModuleStats
  ├── module_id: str
  ├── total_attempts, min_score, max_score, avg_score
  ├── user_score, user_percentile, user_attempts
```

---

## 8. Integration Plan

### 8.1 Integration Order

Streams can be developed in parallel. Integration follows data flow order:

| Phase | What                                 | Prerequisite            |
| ----- | ------------------------------------ | ----------------------- |
| I-1   | Stream 1 + Stream 5 (upload page)    | Stream 1 done, upload page done |
| I-2   | Stream 2 + Stream 5 (module viewer)  | I-1, Stream 2 done      |
| I-3   | Stream 3 + Stream 5 (quiz page)      | I-2, Stream 3 done      |
| I-4   | Stream 4 + Stream 5 (results page)   | I-3, Stream 4 done      |
| I-5   | End-to-end smoke test                | I-4                     |

### 8.2 Integration Smoke Tests

1. **Upload → Parse:** Upload a sample PDF, verify `Document` is created with correct sections/images.
2. **Parse → Learn:** Feed `Document` to content engine, verify `LearningModule` has topics with content and questions.
3. **Learn → Quiz:** Generate `QuestionBank` from module, assemble a quiz, verify questions appear.
4. **Quiz → Results:** Submit answers, verify `QuizResult` is scored correctly and saved to DB.
5. **Results → Analytics:** After 3+ attempts, verify min/max/avg stats are correct.
6. **Full flow:** Upload → Learn → Quiz → Results → Retake (verify different questions).

---

## 9. Non-Functional Requirements

### 9.1 File Constraints

- Maximum upload file size: **50 MB**
- Supported formats: `.pdf`, `.pptx`, `.docx`
- Reject unsupported formats with a clear error message.

### 9.2 LLM Usage

- All LLM calls go through `content/llm_client.py` — no direct SDK imports elsewhere.
- Token budget per module generation: configurable, default **100,000 tokens** (input + output combined).
- Timeout per LLM call: **60 seconds**.
- On LLM failure: retry once, then surface error to user.

### 9.3 Performance

- Document parsing: < 30 seconds for a 50-page PDF.
- Module generation (LLM): may take 1-3 minutes — show progress to user.
- Quiz assembly (no LLM): < 1 second.

### 9.4 Error Handling

- Parse failures: show "Could not parse this file" with the specific error.
- LLM failures: show "Content generation failed, please try again" with a retry button.
- Database errors: log and show a generic error.

### 9.5 Security (Phase 1 scope)

- **Admin authentication:** Single admin account. Username and password stored in environment variables (`AI_TUTOR_ADMIN_USERNAME`, `AI_TUTOR_ADMIN_PASSWORD`). No multi-admin support in Phase 1.
- **User authentication:** Username-only (no password). Sufficient for analytics tracking in a controlled deployment.
- Uploaded files stored locally — not accessible to other users.
- No LLM API keys in source code — read from environment variables.
- Phase 2 may add proper multi-user auth (e.g., OAuth or a hashed-password users table).

### Appendix B: New Environment Variables (v0.3)

| Variable                    | Purpose                        | Default       |
| --------------------------- | ------------------------------ | ------------- |
| `AI_TUTOR_ADMIN_USERNAME`   | Admin login username           | `admin`       |
| `AI_TUTOR_ADMIN_PASSWORD`   | Admin login password           | (required)    |

---

## 10. Open Questions

- [x] **Question bank persistence** — **Resolved (v0.3):** Question bank is persisted in `modules.question_bank_json`. Retakes reuse the stored bank; no LLM re-call required.
- [x] **Mermaid rendering** — **Resolved (v0.1):** Client-side via `streamlit-mermaid` component. Falls back to `st.code()` if the component is unavailable.
- [x] **Module library** — **Resolved (v0.3):** A persistent module library page (`frontend/module_library_page.py`) lists all admin-published modules. Users select from the library; they do not upload documents themselves.

---

## Appendix A: Environment Variables

| Variable                | Purpose                          | Default (Phase 1)      |
| ----------------------- | -------------------------------- | ---------------------- |
| `AI_TUTOR_LLM_PROVIDER` | LLM provider name               | `anthropic`            |
| `AI_TUTOR_LLM_API_KEY`  | API key for LLM provider        | (required)             |
| `AI_TUTOR_LLM_MODEL`    | Model name                      | `claude-sonnet-4-6`    |
| `AI_TUTOR_DB_PATH`      | SQLite database file path       | `data/ai_tutor.db`     |
| `AI_TUTOR_UPLOAD_DIR`   | Upload directory                | `data/uploads`         |
| `AI_TUTOR_MAX_FILE_MB`  | Max upload size in MB           | `50`                   |
