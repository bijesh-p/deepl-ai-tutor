# AI Tutor — Architecture

> **Version:** 0.8 | **Updated:** 2026-06-14
> Companion to [SPEC.md](SPEC.md).

---

## 1. End-to-End Flow

The sequence below shows what happens from PDF upload to the end of a tutoring session. After upload, two concurrent activities run: a background pipeline that generates content and a LangGraph session that teaches.

```mermaid
---
title: Upload to Tutoring — Sequence
---
sequenceDiagram
    actor Student
    participant UI as Streamlit UI
    participant BG as Background Thread
    participant LG as LangGraph Tutor
    participant LLM as LLM (Claude)
    participant TTS as edge-tts

    Student->>UI: Upload PDF
    UI->>BG: spawn daemon thread
    UI-->>Student: show progress

    BG->>LLM: parse + decompose topics
    BG->>LLM: enrich topic 1
    BG->>LLM: generate diagram
    BG->>TTS: generate audio (mp3)
    BG-->>UI: publish EnrichedTopic 1, set ready=True

    UI->>LG: redirect to Tutor Room
    LG->>LLM: generate diagnostic MCQ
    LG-->>Student: show diagnostic quiz

    Note over BG: topics 2 to N enrich in background

    Student->>LG: submit answers
    LG->>LG: score, set presentation_depth
    LG->>LG: inject EnrichedTopic 1 from pipeline
    LG->>LLM: adapt transcript to depth
    LG-->>Student: slide — diagram + audio + transcript

    Student->>LG: Ask me a question
    LG->>LLM: generate question
    Student->>LG: answer
    LG->>LLM: evaluate answer
    LG-->>Student: feedback or hint

    loop each next topic
        LG->>LG: advance_concept
        LG->>LG: generate_diagnostic
        Student->>LG: answer diagnostic
        LG-->>Student: slide for next topic
    end
```

---

## 2. System Components

Three layers — Streamlit frontend, backend orchestration, and storage — connected through a shared LLM factory.

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
    BG -->|EnrichedTopic| TUTOR
    TUTOR --> LG
    BG --> LLM
    BG --> TTS
    LG --> LLM
    TTS --> AUDIO
    BG --> DB
    LIB --> DB
```

---

## 3. Content Pipeline

The pipeline runs in a daemon thread. It publishes each `EnrichedTopic` to `st.session_state["pipeline_progress"]` immediately on completion. The UI redirects to the Tutor Room after topic 1 is ready (~30 s); remaining topics enrich in the background.

**Total LLM cost:** 3N + 2 calls + N TTS calls for N topics.

```mermaid
---
title: Pipeline Steps
---
flowchart LR
    PDF([PDF]) --> PARSE[Parse]
    PARSE --> DECOMP[Decompose]
    DECOMP --> ENRICH[Enrich]
    ENRICH --> DIAG[Diagram]
    DIAG --> AUDIO[Audio TTS]
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
| `audio_path` | edge-tts — mp3 narration in `data/audio/` |

---

## 4. LangGraph Tutor

LangGraph is the primary entry point for every tutoring session. Nodes are dispatched manually (not via `graph.invoke()`) so Streamlit can render between each step.

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

**How it works:**

- `generate_diagnostic` creates 3–5 MCQ from topic title and summary only — no enriched content needed, so it runs immediately while the pipeline is still working.
- `evaluate_diagnostic` scores answers and sets `presentation_depth`: below 0.4 → beginner; 0.4–0.7 → intermediate; above 0.7 → advanced.
- `present_concept` checks if the pipeline has delivered `EnrichedTopic` for this concept. If yes, uses its diagram, audio, and top concepts. If not yet ready, generates a lightweight slide from title and summary.
- After mastering a concept, the loop returns to `generate_diagnostic` for the next topic.

---

## 5. LLM Factory

All LLM calls go through a single factory. Callers use Anthropic-format tool schemas; adapters translate for each backend.

| Adapter | Backend | Notes |
|---|---|---|
| `AnthropicAdapter` | Anthropic API | Prompt caching on document blocks |
| `PortkeyAdapter` | Portkey → Vertex AI | Same caching; routes via Portkey gateway |
| `OllamaAdapter` | Ollama (local) | Translates tool schema to OpenAI function format |

---

## 6. Database Schema

```mermaid
---
title: SQLite Tables
---
erDiagram
    users ||--o{ modules : creates
    users ||--o{ quiz_attempts : attempts
    modules ||--o{ quiz_attempts : tested_on
    users ||--o{ topic_mastery : tracks
    modules ||--o{ topic_mastery : covers

    users { TEXT user_id PK; TEXT username }
    modules { TEXT module_id PK; TEXT title }
    quiz_attempts { TEXT attempt_id PK; INTEGER score }
    topic_mastery { TEXT topic_id; INTEGER mastered }
```

---

## 7. Page Navigation

Upload is the only generation entry point. Module Library gives access to previously generated modules.

```mermaid
---
title: Page Navigation
---
flowchart LR
    UPLOAD[Upload] -->|topic 1 ready| TUTOR[Tutor Room]
    UPLOAD -->|existing module| LIB[Module Library]
    LIB -->|select| TUTOR
    LIB -->|generate new| UPLOAD
    TUTOR -->|take quiz| QUIZ[Quiz]
    QUIZ --> RESULTS[Results]
    RESULTS --> LIB
```
