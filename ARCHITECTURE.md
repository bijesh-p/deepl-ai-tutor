# AI Tutor — Architecture

> **Version:** 1.1 | **Updated:** 2026-06-14
> Companion to [SPEC.md](SPEC.md).

---

## 1. End-to-End Flow

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

## 2. System Components

```mermaid
---
title: System Components
---
flowchart LR
    subgraph Frontend
        UP[Upload Page]
        TUTOR[Tutor Room]
        LIB[Module Library]
    end

    subgraph Backend
        BG[Pipeline Thread]
        LG[LangGraph Tutor]
        LLM[LLMFactory]
        TTS[edge-tts]
    end

    subgraph Storage
        DB[(SQLite)]
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
    TUTOR -->|save profile| DB
    LIB --> DB
```

---

## 3. Content Pipeline

The pipeline runs in a daemon thread. It publishes each `EnrichedTopic` immediately on completion. The UI redirects to the Tutor Room after topic 1 is ready (~30 s). **End Session signals the abort event — the thread exits at the next checkpoint.**

**Total LLM cost:** 3N + 2 calls + N TTS calls for N topics.

**Audio narration is diagram-aware:** the TTS script opens by describing what the diagram shows, then continues with the concept explanation — speech and image are connected.

```mermaid
---
title: Pipeline Steps
---
flowchart LR
    PDF([PDF]) --> PARSE[Parse]
    PARSE --> DECOMP[Decompose]
    DECOMP --> ENRICH[Enrich]
    ENRICH --> DIAG[Diagram]
    DIAG --> SCRIPT[Narration Script\ndiagram + transcript]
    SCRIPT --> AUDIO[Audio TTS]
    AUDIO --> PUB[Publish Topic]
    PUB -->|topic 1| REDIRECT[Redirect to Tutor]
    PUB -->|loop| ENRICH
    ENRICH -->|all done| QUIZ[Quiz Bank]
    QUIZ --> SAVE[Save SQLite]
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

## 4. Personalised User Profile

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

**Profile data stored per user:**

| Field | Meaning |
|---|---|
| `overall_depth` | Last presentation depth (`beginner`/`intermediate`/`advanced`) |
| `topic_mastery` | JSON map of `topic_id → mastered` across all modules |
| `module_visits` | JSON map of `module_id → last_visited` |
| `last_seen` | Timestamp of last session |

On return: `presentation_depth` is initialised from `overall_depth`. Topics already marked mastered are shown as complete but can be revisited.

---

## 5. LangGraph Tutor

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
    ROUTER -->|yes, more| GD
    ROUTER -->|yes, done| DONE[session_complete]
    ROUTER -->|no, attempts < 3| HINT[provide_hint]
    ROUTER -->|no, attempts >= 3| SF[simplify_foundations]
    HINT --> AQ
    SF --> AQ
```

**Key behaviours:**

- `generate_diagnostic` uses only topic title and summary — no enriched content needed, runs immediately.
- `evaluate_diagnostic` scores answers and sets `presentation_depth`. Starting depth is seeded from user profile.
- `present_concept` uses `EnrichedTopic` assets (diagram, audio, top concepts) if the pipeline delivered them; falls back to LLM-generated slide.
- On End Session, `save_user_profile` is called with the final `presentation_depth` and all mastered topics.

---

## 6. LLM Factory

All LLM calls go through a single factory. Callers use Anthropic-format tool schemas; adapters translate for each backend.

| Adapter | Backend | Notes |
|---|---|---|
| `AnthropicAdapter` | Anthropic API | Prompt caching on document blocks |
| `PortkeyAdapter` | Portkey → Vertex AI | Same caching; routes via Portkey gateway |
| `OllamaAdapter` | Ollama (local) | Translates tool schema to OpenAI function format |

The same factory is used by the **DeepEval judge** — eval metrics use whichever provider is selected in the sidebar, with no separate API key.

---

## 7. MCP Tool Servers

Three standalone MCP servers expose storage, document parsing, and assessment tools. All backend code accesses these capabilities exclusively through `MCPClient` — no direct imports of `chromadb`, `fitz`, or SQLite outside the servers.

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

**Server responsibilities:**

| Server | Tools | Dependency |
|---|---|---|
| `document_server` | `extract_text_from_pdf`, `parse_images` | PyMuPDF |
| `assessment_server` | `validate_json_schema`, `evaluate_taxonomy` | Pure Python |
| `storage_server` | `save_module_to_db`, `upsert_to_vector_db`, `query_vector_db` | SQLite, ChromaDB, sentence-transformers |

MCP servers run as child processes started by `MCPClient`. They communicate over stdio using the MCP protocol. This means the storage layer can be replaced or scaled independently without touching pipeline or tutor code.

---

## 8. Database Schema

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

    users { TEXT user_id PK; TEXT username }
    user_profiles { TEXT user_id PK; TEXT overall_depth; TEXT topic_mastery_json; TEXT module_visits_json; TEXT last_seen }
    modules { TEXT module_id PK; TEXT title }
    quiz_attempts { TEXT attempt_id PK; INTEGER score }
    topic_mastery { TEXT topic_id; INTEGER mastered; INTEGER attempts }
```

---

## 9. Page Navigation

```mermaid
---
title: Page Navigation
---
flowchart LR
    UPLOAD[Upload] -->|topic 1 ready| TUTOR[Tutor Room]
    UPLOAD -->|existing module| LIB[Module Library]
    LIB -->|select| TUTOR
    LIB -->|generate new| UPLOAD
    TUTOR -->|End Session → abort + save| LIB
    TUTOR -->|take quiz| QUIZ[Quiz]
    QUIZ --> RESULTS[Results]
    RESULTS --> LIB
```

---

## 10. LLM Observability and Evaluation

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

### Running Phoenix Locally

```bash
# Start Phoenix trace server (keeps running in background)
uv run python -m phoenix.server.main serve

# Or via the installed CLI
uv run phoenix serve
```

Phoenix UI is then available at `http://localhost:6006`.

### Environment Variables

| Variable | Value | Purpose |
|---|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:6006/v1/traces` | Route OTEL spans to local Phoenix |
| `LANGCHAIN_TRACING_V2` | `true` | Enable LangSmith tracing (optional) |
| `LANGCHAIN_API_KEY` | `ls-...` | LangSmith API key (optional) |
| `LANGCHAIN_PROJECT` | `ai-tutor` | LangSmith project name (optional) |

### Code Organisation

```
backend/
└── observability/
    ├── __init__.py        # setup_tracing() — call once at app startup
    ├── tracer.py          # get_tracer() helper used across pipeline steps
    └── eval_runner.py     # run_session_evals() — called by tutor_room on End Session
```

`setup_tracing()` is called from `app.py` before any LLM calls. It registers the OTLP exporter, instruments the Anthropic SDK, and optionally enables LangSmith.
