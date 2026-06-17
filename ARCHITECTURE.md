# AI Tutor — Architecture

> **Version:** 1.4 | **Updated:** 2026-06-17
> Companion to [SPEC.md](SPEC.md).

---

## 0. System Overview

### Problem

Static documents (PDFs, PowerPoint slides, Word docs) lead to passive learning and poor retention. Manually creating adaptive, interactive learning content is expensive, slow to update, and impossible to personalise at scale.

### Solution

AI Tutor is a web platform that transforms uploaded documents into interactive, adaptive learning experiences:

1. **Any user** uploads a PDF, PPTX, or DOCX → a background pipeline (decompose → enrich → diagrams → audio → questions) generates a structured learning module; first topic is visible within ~30 seconds. Every pipeline step reports structured, user-actionable errors with retry / partial-recovery options instead of a raw stack trace.
2. **Users** browse the module library → work through enriched content with diagram-first slides, audio narration, and inline questions, then take a quiz.
3. **Adaptive Tutor** (LangGraph) opens with a diagnostic quiz to calibrate depth, then walks through each concept as a slide, follows up with targeted questions, provides hints (grounded in ChromaDB-retrieved context) when the student struggles, and simplifies foundations after repeated failures. Sessions persist mid-concept so a student can close the tab and resume later.
4. **Admin mode** lets an admin publish curated modules to a shared library (separate SQLite DB) so all users can access them without generating their own. Login has separate User (no password) and Admin (password-gated) tabs.
5. A **Mastery Report** page shows per-topic mastery, attempts, and difficulty for any module a user has studied, alongside a cohort comparison.
6. An **Observability** dashboard links out to Arize Phoenix traces and shows DeepEval quality metrics per session.

### High-Level Component Map

```
Streamlit Frontend (entry point: app.py)
    ├── Login Page ──→ User tab (no password) | Admin tab (password) ──→ per-user DB
    ├── Upload & Generate ──→ Background Pipeline (JIT, per-step error recovery) ──→ SQLite + ChromaDB
    ├── Module Library ──→ My Modules (SQLite) + Shared Library (published_modules)
    ├── Module Viewer / Quiz / Results ──→ SQLite
    ├── Tutor Room ──→ LangGraph Graph ──→ SQLite (resume + mastery) + ChromaDB
    ├── Mastery Report ──→ per-topic + cohort mastery (SQLite)
    ├── Observability ──→ Phoenix link + DeepEval metrics (SQLite eval_results)
    │                       ↕
    │              MCP Tool Servers
    │           (document, assessment, storage)
    │                       ↕
    │                  LLMFactory
    │           (anthropic | portkey | ollama)
    └── System Check Page ──→ env + package validation
```

### Tech Stack

| Layer | Technology | Phase introduced |
|---|---|---|
| Frontend | Streamlit (multi-page, single `app.py` router) | 1 |
| Content generation | Direct LLM pipeline (sliding-window + JIT) | 2 |
| Adaptive tutor | LangGraph state machine | 2 |
| LLM providers | Anthropic SDK, Portkey, Ollama (OpenAI-compat) | 1 / 2 / 2 |
| LLM abstraction | Strategy + factory pattern (`BaseLLMClient`, `LLMFactory`) | 2 |
| Tool protocol | MCP (Model Context Protocol) | 2 |
| Vector store | ChromaDB + `sentence-transformers` (`all-MiniLM-L6-v2`) | 2 |
| Relational DB | SQLite (`sqlite3` stdlib), per-user DB + shared DB for published modules | 1 / 2 / 3 |
| Document parsing | PyMuPDF (PDF), `python-pptx`, `python-docx` | 1 / 3 (Phase 35) |
| Diagrams | Mermaid (LLM-generated, diagram-first approach) | 1 / 2 |
| Audio TTS | `edge-tts` (Microsoft Edge voices, offline) | 2 |
| LLM quality evals | DeepEval (LLM-as-judge, async, per session) | 2 |
| Observability | Arize Phoenix + OTEL (`opentelemetry-sdk`), dedicated dashboard page | 2 / 3 (Phase 37) |
| Package manager | `uv` | 1 |
| Python | 3.14+ | 1 |

---

## 1. Directory Structure

```
ai-tutor-platform/
│
├── .env.example                        # All env var templates
├── README.md                           # Setup, architecture, quickstart
├── pyproject.toml                      # Unified dependencies (uv)
├── SPEC.md
├── ARCHITECTURE.md
├── CLAUDE.md
├── app.py                              # Entry point: session init, sidebar, page router
│
├── mcp_servers/                        # TOOL LAYER — MCP microservices
│   ├── __init__.py
│   ├── document_server/                # Tools: extract_text_from_pdf, parse_images,
│   │                                    #        extract_text_from_pptx, extract_text_from_docx
│   ├── assessment_server/              # Tools: validate_json_schema, evaluate_taxonomy
│   └── storage_server/                 # Tools: upsert_to_vector_db, save_module_to_db, query_vector_db
│
├── backend/                            # CORE LOGIC LAYER
│   ├── core/
│   │   ├── mcp_client.py              # Helper to discover and call MCP tools
│   │   └── llm_client/               # Provider factory + adapters
│   │       ├── base.py               # Abstract BaseLLMClient
│   │       ├── factory.py            # LLMFactory.create(provider) -> BaseLLMClient
│   │       └── adapters/
│   │           ├── anthropic_adapter.py
│   │           ├── portkey_adapter.py
│   │           └── ollama_adapter.py
│   │
│   ├── ingestion/                     # Document parsers
│   │   ├── models.py                  # Document, Section, ExtractedImage dataclasses
│   │   ├── pdf_parser.py
│   │   ├── pptx_parser.py             # Phase 35
│   │   ├── docx_parser.py             # Phase 35
│   │   └── image_extractor.py
│   │
│   ├── content/                       # Content generation pipeline
│   │   ├── models.py                  # LearningModule, EnrichedTopic, Topic, Diagram, Question
│   │   ├── sliding_pipeline.py        # Sliding-window decomposition + JIT enrichment;
│   │   │                              # per-topic enrich failures are caught and skipped (Phase 36)
│   │   ├── diagram_generator.py       # Diagram-first: Mermaid or bullet fallback
│   │   ├── content_enricher.py        # Anchor-grounded explanation generation
│   │   ├── inline_question_gen.py     # Per-topic inline comprehension questions
│   │   └── audio_generator.py         # edge-tts narration per topic
│   │
│   ├── interactive_tutor/             # ADAPTIVE TUTOR — LangGraph
│   │   ├── __init__.py
│   │   └── graph.py                   # GraphState TypedDict, all node functions,
│   │                                  # build_tutor_graph() with conditional router
│   │
│   ├── observability/                 # LLM quality + tracing
│   │   ├── tracer.py                  # OTEL setup → Arize Phoenix (+ optional LangSmith)
│   │   └── eval_runner.py             # DeepEval metrics (async, fire-and-forget per session)
│   │
│   ├── quiz/                          # Quiz engine (Phase 1 core)
│   │   ├── models.py
│   │   ├── question_bank.py
│   │   ├── difficulty.py
│   │   ├── assembler.py
│   │   └── evaluator.py
│   │
│   └── analytics/                     # Persistence + stats
│       ├── db.py                      # Schema + migrations (per-user DB and shared DB)
│       ├── auth.py                    # Admin username/password checks (Phase 32)
│       ├── models.py
│       ├── persistence.py             # CRUD incl. tutor_sessions, topic_mastery, published_modules
│       └── stats.py
│
├── frontend/                          # PRESENTATION LAYER (pages rendered by app.py)
│   ├── login_page.py                  # Two-mode login: User tab / Admin tab (Phase 32)
│   ├── upload_page.py                 # Upload PDF/PPTX/DOCX, run background JIT pipeline,
│   │                                  # per-step error UI + partial-failure recovery (Phase 36)
│   ├── module_library_page.py         # My Modules + Shared Library, admin publish controls (Phase 32)
│   ├── module_viewer.py               # Topics with diagram-first slides, inline audio, inline Qs
│   ├── quiz_page.py
│   ├── results_page.py
│   ├── tutor_room.py                  # LangGraph tutor: diagnostic → slides → Q&A,
│   │                                  # session resume banner (Phase 33), error recovery UI (Phase 36)
│   ├── mastery_report_page.py         # Per-topic + cohort mastery report (Phase 40)
│   ├── observability_page.py          # Phoenix link + DeepEval metrics dashboard (Phase 37)
│   └── system_check_page.py           # Verify env + packages
│
├── tests/
│   ├── test_ingestion/
│   ├── test_content/                  # incl. test_llm_client.py, test_sliding_pipeline.py
│   ├── test_quiz/
│   ├── test_analytics/
│   ├── test_tutor/                    # LangGraph node tests with mock LLM (Phase 38)
│   ├── test_mcp/
│   └── fixtures/
│
└── data/                              # Runtime data (gitignored)
    ├── uploads/
    ├── generated/
    ├── ai_tutor.db                    # per-user DB (default path)
    ├── shared/ai_tutor.db             # published_modules — admin-shared library (Phase 32)
    └── chroma/                        # ChromaDB persistent store
```

---

## 2. End-to-End Flow

After upload, two concurrent activities run: a background pipeline that generates content and a LangGraph session that teaches. The session is personalised — the student's name keys a persistent profile that carries expertise, preferred depth, and topic mastery across visits.

```mermaid
---
title: Upload to Tutoring — Sequence
---
sequenceDiagram
    actor Student
    participant UI as Streamlit UI
    participant DB as SQLite
    participant BG as Background Thread
    participant LG as LangGraph Tutor
    participant LLM as LLM (Claude)
    participant TTS as edge-tts

    Student->>UI: Enter name + Upload PDF
    UI->>DB: save_user (upsert by username)
    DB-->>UI: user_id + prior profile (depth, mastery)

    UI->>BG: spawn daemon thread
    BG->>LLM: parse + decompose topics
    BG->>LLM: enrich topic 1
    BG->>LLM: generate diagram
    BG->>TTS: narrate diagram then transcript
    BG-->>UI: publish EnrichedTopic 1, ready=True

    UI->>LG: redirect to Tutor Room
    Note over LG: pre-seed depth from prior profile
    LG->>LLM: generate diagnostic MCQ
    LG-->>Student: show diagnostic quiz

    Note over BG: topics 2..N enrich in background

    Student->>LG: submit answers
    LG->>LG: score → update presentation_depth
    LG->>LG: inject EnrichedTopic 1 from pipeline
    LG->>LLM: adapt transcript to depth
    LG-->>Student: slide — diagram + audio + transcript

    Note over Student,LG: Q&A loop per topic

    Student->>UI: End Session
    UI->>BG: abort_event.set()
    UI->>DB: save_user_profile (depth + mastery)
    UI->>UI: navigate to Module Library
```

---

## 3. System Components

```mermaid
---
title: System Components
---
flowchart LR
    subgraph Frontend
        UP[Upload Page]
        TUTOR[Tutor Room]
        LIB[Module Library]
        MR[Mastery Report]
        OBS[Observability]
    end

    subgraph Backend
        BG[Pipeline Thread]
        LG[LangGraph Tutor]
        LLM[LLMFactory]
        TTS[edge-tts]
    end

    subgraph Storage
        DB[(SQLite\nper-user)]
        SHARED[(SQLite\nshared/published)]
        AUDIO[data/audio/]
    end

    UP -->|spawn| BG
    UP -->|load profile| DB
    BG -->|EnrichedTopic| TUTOR
    TUTOR --> LG
    BG --> LLM
    BG --> TTS
    LG --> LLM
    TTS --> AUDIO
    BG --> DB
    TUTOR -->|save session + mastery| DB
    LIB --> DB
    LIB -->|publish/unpublish, admin only| SHARED
    MR --> DB
    OBS --> DB
```

---

## 4. Content Pipeline

The pipeline runs in a daemon thread. It publishes each `EnrichedTopic` immediately on completion. The UI redirects to the Tutor Room after topic 1 is ready (~30 s). **End Session signals the abort event — the thread exits at the next checkpoint.**

**Total LLM cost:** 3N + 2 calls + N TTS calls for N topics.

**Audio narration is diagram-aware:** the TTS script opens by describing what the diagram shows, then continues with the concept explanation — speech and image are connected.

**Per-step error handling (Phase 36):** `_run_pipeline_bg` in `upload_page.py` wraps each step (parse / LLM-connect / enrich / quiz / save) in its own try/except. A `_fail()` helper records `state="failed"`, the `failed_step`, a user-facing message, and the raw exception (`error_detail`) for a collapsible technical expander. `progress["module"]` is set as soon as enrichment finishes — *before* quiz/save run — so a failure in either of those later steps still leaves enough state for the UI to offer **"Learn with N topic(s) →"** (continue with what was generated) alongside **"Retry from scratch"**. Inside `sliding_pipeline._enrich_one`, a single topic's `enrich()` call is itself guarded — one bad topic is skipped and logged rather than killing the whole run.

```mermaid
---
title: Pipeline Steps
---
flowchart LR
    PDF([PDF]) --> PARSE[Parse]
    PARSE --> DECOMP[Sliding-window\nDecompose]
    DECOMP --> ANCHOR[Slide Anchor\nMermaid or bullets]
    ANCHOR --> ENRICH[Enrich\nanchor-grounded]
    ENRICH --> IQ[Inline\nQuestions]
    IQ --> AUDIO[Audio TTS]
    AUDIO --> PUB[Publish Topic]
    PUB -->|topic 1| REDIRECT[Redirect to Tutor]
    PUB -->|loop| ANCHOR
    ENRICH -->|all done| QUIZ[Quiz Bank]
    QUIZ --> SAVE[Save SQLite]
```

### 4.1 Sliding-Window Decomposition

- Accumulate ~500 words at a time; LLM assesses whether the window is a teachable concept
- Force-publish after 1500 words; fallback if nothing published by end of doc
- Output: `list[Topic]`

### 4.2 Slide Anchor (diagram-first)

Every slide has a visual or structural anchor written before the explanation:

| Anchor type | When used | Rendered as |
|---|---|---|
| Mermaid diagram | LLM produces valid Mermaid code | `streamlit-mermaid` component |
| Bulleted key points | Diagram fails or produces empty output | `st.markdown` bullet list |

The anchor is passed to `enrich()` so the explanation explicitly references it. The explanation must not introduce concepts not visible in the anchor.

### 4.3 Just-in-Time Delivery

```
User uploads PDF
    ├─ Parse PDF (~1s)
    ├─ Decompose into topics (1 LLM call, ~5–10s)
    ├─ Enrich topic 1 (3 LLM calls + TTS, ~15–30s)
    │   → redirect to module viewer
    ├─ [background] Enrich topics 2…N
    │   → each appears in viewer as it completes (@st.fragment poll)
    └─ [background] Generate quiz bank
        → "Take Quiz" button enables when ready
```

**EnrichedTopic fields:**

| Field | Source |
|---|---|
| `top_concepts` (2–3 strings) | Enricher LLM — key ideas shown as callout |
| `content_md` | Enricher LLM — conversational Markdown explanation |
| `key_takeaways` | Enricher LLM — 3–5 bullet summary |
| `diagrams` | Diagram LLM — Mermaid flowchart, max 6 nodes |
| `inline_questions` | Question LLM — 2 SCQ/MCQ per topic |
| `audio_path` | edge-tts — narrates diagram then transcript |

---

## 5. LLM Factory

All LLM calls go through a single factory. Callers always pass Anthropic-format tool schemas; adapters translate for each backend.

```mermaid
---
title: LLM Client Class Hierarchy
---
classDiagram
    class BaseLLMClient {
        <<abstract>>
        +generate(prompt, system, tool_schema, context_blocks) str|dict
        +make_context_blocks(text) list
    }
    class AnthropicAdapter {
        -_client: anthropic.Anthropic
        +generate(...)
        +make_context_blocks(text) cached_blocks
    }
    class PortkeyAdapter {
        -_client: portkey_ai.Portkey
        +generate(...)
        +make_context_blocks(text) cached_blocks
    }
    class OllamaAdapter {
        -_client: openai.OpenAI
        +generate(...)
        +make_context_blocks(text) plain_prefix
    }
    class LLMFactory {
        +create(provider, **kwargs) BaseLLMClient
    }
    BaseLLMClient <|-- AnthropicAdapter
    BaseLLMClient <|-- PortkeyAdapter
    BaseLLMClient <|-- OllamaAdapter
    LLMFactory --> BaseLLMClient
```

### Adapters

| Adapter | SDK | Tool schema | Caching |
|---|---|---|---|
| `AnthropicAdapter` | `anthropic` | Anthropic native (`input_schema`) | `cache_control` blocks |
| `PortkeyAdapter` | `portkey_ai` | Anthropic native | `cache_control` blocks |
| `OllamaAdapter` | `openai` (compat) | OpenAI function format (translated internally) | No caching |

`LLMFactory.create(provider)` reads `AI_TUTOR_LLM_PROVIDER` from env if provider is `None`. The same factory is used by the **DeepEval judge** — eval metrics use whichever provider is selected in the sidebar, with no separate API key.

---

## 6. MCP Tool Servers

Three standalone MCP servers expose storage, document parsing, and assessment tools. All backend code accesses these capabilities exclusively through `MCPClient` — no direct imports of `chromadb`, `fitz`, or SQLite outside the servers. MCP servers run as child processes started by `MCPClient`, communicating over stdio.

```mermaid
---
title: MCP Tool Servers
---
flowchart LR
    subgraph Callers
        PIPE[Pipeline Steps]
        TUTOR[LangGraph Nodes]
    end

    MC[MCPClient]

    subgraph document_server
        T1[extract_text_from_pdf]
        T2[parse_images]
        T1b[extract_text_from_pptx]
        T1c[extract_text_from_docx]
    end

    subgraph assessment_server
        T3[validate_json_schema]
        T4[evaluate_taxonomy]
    end

    subgraph storage_server
        T5[save_module_to_db]
        T6[upsert_to_vector_db]
        T7[query_vector_db]
    end

    PIPE & TUTOR --> MC
    MC --> document_server & assessment_server & storage_server
    document_server --> PyMuPDF[PyMuPDF]
    storage_server --> SQLite[(SQLite)]
    storage_server --> ChromaDB[(ChromaDB)]
```

### document_server tools

| Tool | Signature | Description |
|---|---|---|
| `extract_text_from_pdf` | `(file_path: str, max_pages: int = 4) -> str` | Parse PDF via PyMuPDF, return `Document.to_json()` |
| `parse_images` | `(file_path: str, max_pages: int = 4) -> str` | Extract embedded images, save as PNG |
| `extract_text_from_pptx` | `(file_path: str, max_slides: int = 16) -> str` | Parse PPTX via `python-pptx`, return `Document.to_json()` (Phase 35) |
| `extract_text_from_docx` | `(file_path: str, max_sections: int = 16) -> str` | Parse DOCX via `python-docx`, return `Document.to_json()` (Phase 35) |

### assessment_server tools

| Tool | Signature | Description |
|---|---|---|
| `validate_json_schema` | `(data: dict, schema_name: str) -> ValidationResult` | Assert output matches expected schema |
| `evaluate_taxonomy` | `(question: dict) -> TaxonomyTag` | Tag a question with Bloom's taxonomy level |

### storage_server tools

| Tool | Signature | Description |
|---|---|---|
| `save_module_to_db` | `(module_id, title, source_filename, module_json, question_bank_json, created_by, db_path=None) -> str` | Delegates to `backend.analytics.db.get_db(db_path)` + `persistence.save_module(...)` (Phase 39) — same per-user DB the rest of the app reads |
| `upsert_to_vector_db` | `(texts: list[str], metadata: list[dict], collection: str) -> None` | Embed and store chunks in ChromaDB |
| `query_vector_db` | `(query: str, collection: str, n_results: int) -> list[dict]` | Semantic search over stored chunks |

`save_module_to_db`'s optional `db_path` follows the same delegation pattern introduced for `extract_text_from_pdf` in Phase 30 — `frontend/upload_page.py` calls it through `mcp_client` instead of importing `persistence.save_module` directly. Publishing/unpublishing a module to the shared library (`publish_module`, `unpublish_module`, `get_published_modules`, `load_published_module`) is **not** MCP-routed — `module_library_page.py` calls `backend.analytics.persistence` directly against the shared DB (`get_shared_db()`).

### MCPClient interface (`backend/core/mcp_client.py`)

```python
class MCPClient:
    def call(self, server: str, tool: str, **kwargs) -> dict: ...
    def list_tools(self, server: str) -> list[str]: ...
```

---

## 7. LangGraph Tutor

LangGraph is the primary entry point for every tutoring session. Nodes are dispatched manually so Streamlit can render between steps.

```mermaid
---
title: LangGraph Node Flow
---
flowchart TD
    START --> GD[generate_diagnostic]
    GD --> WAIT([Student answers])
    WAIT --> ED[evaluate_diagnostic]
    ED --> PC[present_concept\nslide output]
    PC --> AQ[ask_question]
    AQ --> WAIT2([Student answers])
    WAIT2 --> ER[evaluate_response]
    ER --> ROUTER{mastered?}
    ROUTER -->|yes, more| AC[advance_concept]
    AC --> PC
    ROUTER -->|yes, done| DONE[session_complete]
    ROUTER -->|no, attempts < 3| HINT[provide_hint]
    ROUTER -->|no, attempts >= 3| SF[simplify_foundations]
    HINT --> AQ
    SF --> AQ
```

### Graph State (`backend/interactive_tutor/graph.py`)

```python
class GraphState(TypedDict):
    # Current position
    current_concept: str
    concept_content: str           # enriched Markdown (from pipeline or generated)
    concept_summary: str           # topic summary from decomposer
    current_question: dict | None
    student_answer: str

    # Diagnostic
    diagnostic_questions: list[dict]   # MCQ questions shown before first slide
    diagnostic_answers: list[int]      # student's choices
    diagnostic_score: float            # 0.0–1.0
    presentation_depth: str            # "beginner" | "intermediate" | "advanced"

    # Slide content
    topic_diagram: str             # Mermaid code for current concept
    topic_audio_path: str          # path to mp3 narration
    topic_top_concepts: list[str]  # 2–3 key concept labels
    enriched_topic: dict | None    # EnrichedTopic asdict — injected by UI when ready

    # Tracking
    attempts: int
    concept_mastered: bool
    mastered_concepts: list[str]
    remaining_concepts: list[str]

    # Conversation
    chat_history: list[dict]
```

### Nodes

| Node | What it does |
|---|---|
| `generate_diagnostic` | Generates 3 MCQ questions using only topic title + summary — runs immediately, no enriched content needed |
| `evaluate_diagnostic` | Scores answers; sets `presentation_depth` (beginner / intermediate / advanced), seeded from user profile |
| `present_concept` | Delivers slide: diagram + audio (if ready) + depth-calibrated transcript. Falls back to a ChromaDB-retrieved chunk (Phase 34, query = concept title) when `enriched_topic`/`concept_content` is empty in state — e.g. on session resume before the pipeline reaches this topic — then to a fully LLM-generated slide if ChromaDB has nothing either |
| `ask_question` | Generates a targeted question assessing the current concept |
| `evaluate_response` | Analyses answer for specific misconceptions; sets `concept_mastered`; increments `attempts` |
| `provide_hint` | Queries `storage_server.query_vector_db` (filtered by `module_id`, Phase 34) to ground a hint in retrieved chunks (non-fatal on error), tailored to the student's specific error — does not reveal the answer |
| `simplify_foundations` | After 3 failed attempts: breaks concept into building blocks, re-teaches from basics |
| `advance_concept` | Pops next concept from `remaining_concepts`; resets per-concept tracking |

### Session Resume and Mastery Persistence (Phase 33/40)

`tutor_room.py` calls graph nodes manually via `_run_node()` — never through `graph.invoke(state, config=...)` — so a real LangGraph `SqliteSaver` checkpointer (which hooks `.invoke()`/`config`/`thread_id`) doesn't fit without rewriting the control flow. Instead, a lightweight `tutor_sessions` table stores the serialized `GraphState` dict plus the UI `phase`, keyed by `(user_id, module_id)`, upserted after each settled render and deleted on session completion:

```sql
CREATE TABLE IF NOT EXISTS tutor_sessions (
    user_id    TEXT NOT NULL,
    module_id  TEXT NOT NULL,
    state_json TEXT NOT NULL,
    phase      TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, module_id)
);
```

On re-entering the Tutor Room for the same module, `_maybe_resume_session()` loads this row and shows a **"Resuming your previous session on this module."** banner with a **"Restart from scratch"** button. Per-topic mastery is written incrementally to `topic_mastery` — once per concept when it's mastered, or as an `mastered=0` "in progress" row if the session ends mid-concept — independent of (and in addition to) the end-of-session summary blob in `user_profiles.topic_mastery_json`:

```sql
CREATE TABLE IF NOT EXISTS topic_mastery (
    user_id       TEXT NOT NULL,
    module_id     TEXT NOT NULL,
    topic_id      TEXT NOT NULL,
    mastered      INTEGER NOT NULL DEFAULT 0,
    difficulty    TEXT NOT NULL DEFAULT 'medium',
    attempts      INTEGER NOT NULL DEFAULT 0,
    last_updated  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, module_id, topic_id)
);
```

`frontend/mastery_report_page.py` (Phase 40, reachable via a "Mastery Report" button per module in Module Library) renders this table per-topic alongside a cohort comparison (`get_cohort_mastery()` — % of all users who mastered each topic).

### Tutor Error Handling (Phase 36)

`_run_node()` wraps each node call in try/except. On an exception it stores `{"node": node_name, "detail": str(exc)}` in `st.session_state["tutor_error"]` and calls `st.rerun()` — the `RerunException` aborts the rest of the current button-handler chain so no further node runs against stale state. The next render short-circuits to `_render_tutor_error()`, which shows the failing node, a collapsible technical detail, and two recovery actions: **"Try again"** (clears the flag, reruns the same node) and **"Reset session"** (deletes the `tutor_sessions` row via `delete_tutor_session()` and clears all tutor state keys, returning to a fresh diagnostic).

---

## 8. Personalised User Profile

Every student has a persistent profile keyed by username. When they return, the system reloads their prior depth preference and topic mastery so the tutor picks up where they left off.

```mermaid
---
title: Profile Load and Save
---
flowchart LR
    LOGIN[Enter username] --> UPSERT[upsert user]
    UPSERT --> LOAD[load_user_profile]
    LOAD --> SEED[pre-seed depth\nand mastery in state]
    SEED --> TUTOR[Tutor Room]
    TUTOR --> END[End Session]
    END --> SAVE[save_user_profile]
    SAVE --> DB[(SQLite)]
```

| Field | Meaning |
|---|---|
| `overall_depth` | Last presentation depth (`beginner`/`intermediate`/`advanced`) |
| `topic_mastery` | JSON map of `topic_id → mastered` across all modules |
| `module_visits` | JSON map of `module_id → last_visited` |
| `last_seen` | Timestamp of last session |

---

## 9. Frontend Pages

| Page | File | Purpose | Phase |
|---|---|---|---|
| Login | `frontend/login_page.py` | Two tabs: User (no password) / Admin (password-gated); per-user provider/model prefs persisted in SQLite | 2 / 32 |
| Upload | `frontend/upload_page.py` | Upload PDF/PPTX/DOCX, run background JIT pipeline, abort support, per-step error UI + partial-recovery buttons | 2 / 35 / 36 |
| Module Library | `frontend/module_library_page.py` | My Modules (with Mastery Report button) + Shared Library section; admin publish/unpublish controls | 1 / 32 / 40 |
| Module Viewer | `frontend/module_viewer.py` | Diagram-first slides, inline audio player, inline Qs, deferred quiz button | 2 |
| Quiz | `frontend/quiz_page.py` | Difficulty selector, questions, submit | 1 |
| Results | `frontend/results_page.py` | Score, cohort bar chart, per-question breakdown | 1 |
| Tutor Room | `frontend/tutor_room.py` | Diagnostic quiz → slide presentation → Q&A loop with hints; session resume banner; error recovery UI | 2 / 33 / 36 |
| Mastery Report | `frontend/mastery_report_page.py` | Per-topic mastery/difficulty/attempts + cohort comparison for a given module | 40 |
| Observability | `frontend/observability_page.py` | Phoenix trace link + DeepEval per-session metric table + avg score chart | 37 |
| System Check | `frontend/system_check_page.py` | Verify packages + env vars before running | 2 |

The global audio on/off toggle and the Observability sidebar shortcut live in `app.py`'s sidebar, not in a per-page file — they apply across Upload, Tutor Room, and Module Viewer.

### Admin Mode (Phase 32)

- Any user can generate a personal module (existing behaviour) by logging in via the **User** tab — no password
- A user whose username is listed in `AI_TUTOR_ADMIN_USERNAMES` can instead log in via the **Admin** tab, which additionally requires `AI_TUTOR_ADMIN_PASSWORD`, setting `is_admin=True` for the session
- An admin can **publish** one of their own generated modules, copying it into a separate shared SQLite DB (`data/shared/ai_tutor.db`, table `published_modules`); **unpublish** removes it. No edit/delete rights over other users' personal modules
- Published modules appear in a "Shared Library" section in `module_library_page.py`, visible to every user regardless of who generated the module
- The per-user `modules` table also carries `is_published INTEGER DEFAULT 0` so "My Modules" can badge a module as already published

### Page Navigation

```mermaid
---
title: Page Navigation
---
flowchart LR
    LOGIN[Login\nUser / Admin tab] --> UPLOAD[Upload]
    UPLOAD -->|topic 1 ready, or recover partial| TUTOR[Tutor Room]
    UPLOAD -->|existing module| LIB[Module Library]
    LIB -->|select, or resume| TUTOR
    LIB -->|generate new| UPLOAD
    LIB -->|Mastery Report| MR[Mastery Report]
    LIB -->|admin publish/unpublish| LIB
    MR --> LIB
    TUTOR -->|End Session → abort + save| LIB
    TUTOR -->|take quiz| QUIZ[Quiz]
    QUIZ --> RESULTS[Results]
    RESULTS --> LIB
```

`system_check` and `observability` are accessible from the sidebar at any time.

---

## 10. Data Models (Interface Contracts)

### Document (`backend/ingestion/models.py`)

```python
@dataclass
class Section:
    section_id: str; title: str; body: str; level: int
    images: list[ExtractedImage] = field(default_factory=list)

@dataclass
class Document:
    doc_id: str; title: str; source_filename: str
    source_type: SourceType; sections: list[Section]; total_pages: int
```

### Learning Module (`backend/content/models.py`)

```python
@dataclass
class SlideAnchor:
    diagram: Diagram | None          # Mermaid diagram if generation succeeded
    bullets: list[str]               # 4–6 key points if diagram generation failed

@dataclass
class EnrichedTopic:
    topic: Topic; content_md: str; key_takeaways: list[str]
    diagrams: list[Diagram]; inline_questions: list[Question]
    top_concepts: list[str]          # 2–3 key concept labels
    audio_path: str                  # path to edge-tts mp3 narration

@dataclass
class LearningModule:
    module_id: str; title: str; source_doc_id: str
    topics: list[EnrichedTopic]; created_at: str
    is_published: bool = False        # Phase 3: admin can publish to shared library
```

### Quiz (`backend/quiz/models.py`) and Analytics (`backend/analytics/models.py`)

Unchanged from Phase 1 — see source files.

### Analytics additions (Phase 3)

- `get_mastery_report(user_id, module_id) -> MasteryReport` — per-topic mastery, attempts, final difficulty
- `get_cohort_mastery(module_id) -> CohortMastery` — average mastery rate per topic across all users

---

## 11. Database Schema

```mermaid
---
title: SQLite Tables
---
erDiagram
    users ||--o{ modules : creates
    users ||--o{ quiz_attempts : attempts
    users ||--|| user_profiles : has
    modules ||--o{ quiz_attempts : tested_on
    users ||--o{ topic_mastery : tracks
    modules ||--o{ topic_mastery : covers
    users ||--o{ tutor_sessions : resumes
    modules ||--o{ tutor_sessions : tracked_in

    users { TEXT user_id PK; TEXT username }
    user_profiles { TEXT user_id PK; TEXT overall_depth; TEXT topic_mastery_json; TEXT module_visits_json; TEXT last_seen }
    modules { TEXT module_id PK; TEXT title; INTEGER is_published }
    quiz_attempts { TEXT attempt_id PK; INTEGER score }
    topic_mastery { TEXT topic_id; INTEGER mastered; TEXT difficulty; INTEGER attempts }
    tutor_sessions { TEXT user_id PK; TEXT module_id PK; TEXT state_json; TEXT phase }
```

All tables above live in the **per-user DB** (`data/<username>/ai_tutor.db`, or `AI_TUTOR_DB_PATH`). A separate **shared DB** (`AI_TUTOR_SHARED_DB_PATH`, default `data/shared/ai_tutor.db`) holds one standalone table with no cross-DB foreign keys:

```
published_modules { TEXT module_id PK; TEXT title; TEXT module_json; TEXT question_bank_json; TEXT created_by; TEXT published_at }
```

ChromaDB collection `modules` holds one chunk per `EnrichedTopic`. Accessed exclusively through `storage_server` MCP tools — no direct `chromadb` imports outside the server.

---

## 12. LLM Observability and Evaluation

Every LLM call in the system is traced via OpenTelemetry. Traces are sent to a local **Arize Phoenix** server (no account required). After each tutoring session, **DeepEval** runs automated quality metrics. **LangSmith** receives LangGraph traces as a secondary destination via env vars.

### Tool Choices

| Tool | Package | Role |
|---|---|---|
| **Arize Phoenix** | `arize-phoenix` | Local OTLP trace server — UI at `http://localhost:6006` |
| **openinference-instrumentation-anthropic** | `openinference-instrumentation-anthropic` | Auto-patches Anthropic SDK — every `messages.create()` emits a span |
| **openinference-instrumentation-langchain** | `openinference-instrumentation-langchain` | Auto-patches LangGraph node calls |
| **opentelemetry-sdk** | `opentelemetry-sdk` | OTEL tracer provider + context propagation |
| **opentelemetry-exporter-otlp-proto-http** | `opentelemetry-exporter-otlp-proto-http` | HTTP exporter → Phoenix OTLP endpoint |
| **DeepEval** | `deepeval` | Programmatic eval metrics: faithfulness, answer relevancy, contextual precision |
| **LangSmith** | (env vars only, no new package) | Secondary trace destination for LangGraph — `LANGCHAIN_TRACING_V2=true` |

### Trace Flow

```mermaid
---
title: Observability Data Flow
---
flowchart LR
    APP[AI Tutor\nPython process] -->|OTEL spans| EXPORTER[OTLP HTTP\nexporter]
    EXPORTER -->|http://localhost:6006/v1/traces| PHOENIX[Arize Phoenix\nlocal server]
    APP -->|LANGCHAIN_TRACING_V2=true| LANGSMITH[LangSmith\ncloud optional]
    PHOENIX --> UI[Phoenix UI\nhttp://localhost:6006]

    APP -->|after session| EVAL[DeepEval\nevaluate]
    EVAL -->|judge LLM calls| JUDGE[Anthropic Claude\nas eval judge]
    EVAL -->|metrics JSON| DB[(SQLite\neval_results)]
    EVAL --> UI
```

### What Gets Traced

| Span | Source | Key attributes |
|---|---|---|
| `anthropic.messages.create` | openinference auto-patch | model, prompt tokens, completion tokens, latency |
| LangGraph node execution | openinference auto-patch | node name, state diff, duration |
| Pipeline step (enrich / diagram / audio) | manual span via `tracer.start_as_current_span()` | topic title, step name |
| DeepEval eval run | deepeval built-in | metric scores, test case input/output |

### Eval Metrics (DeepEval)

Run after each tutoring session against the slide transcripts and Q&A turns:

| Metric | What it checks |
|---|---|
| `AnswerRelevancyMetric` | Tutor's explanation actually answers the topic (not off-topic) |
| `FaithfulnessMetric` | Transcript content is faithful to the source document (no hallucination) |
| `ContextualRecallMetric` | Key concepts from source appear in the enriched output |
| `GEval` (custom) | Diagnostic question quality — are questions fair for the stated topic? |

### Observability Dashboard Page (Phase 37)

`frontend/observability_page.py` gives a single in-app view of both trace and eval data, instead of requiring the user to leave Streamlit:

1. **Phoenix trace explorer** — derives the Phoenix base URL from `OTEL_EXPORTER_OTLP_ENDPOINT` and renders an `st.link_button` to open the Phoenix UI in a new tab (no embedding — Phoenix's own UI is richer).
2. **DeepEval quality metrics** — calls `get_eval_results()` in `backend/analytics/stats.py` (a `LEFT JOIN` against `modules` for the title), and renders a per-session metric table plus an average-score bar chart.

Reachable from the sidebar (`app.py`) and from a "📊 Observability" button on the Module Library home page.

### Running Phoenix Locally

```bash
uv run phoenix serve
```

Phoenix UI is then available at `http://localhost:6006`.

### Code Organisation

```
backend/
└── observability/
    ├── __init__.py        # setup_tracing() — call once at app startup
    ├── tracer.py          # get_tracer() helper used across pipeline steps
    └── eval_runner.py     # run_session_evals() — called by tutor_room on End Session
```

`setup_tracing()` is called from `app.py` before any LLM calls.
