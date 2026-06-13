# AI Tutor — Architecture Document

> **Version:** 0.5 | **Updated:** 2026-06-12
> Companion to [SPEC.md](SPEC.md).

---

## 1. System Overview

Three layers — presentation, orchestration, and tool services — connected through a unified LLM factory.

```mermaid
---
title: System Architecture
---
flowchart TD
    subgraph Frontend["Streamlit Frontend"]
        UP[Upload & Generate]
        LIB[Module Library]
        LEARN[Module Viewer]
        QUIZ[Quiz Page]
        RES[Results Page]
        TUTOR[Tutor Room]
    end

    subgraph Orchestration["Backend Orchestration"]
        CF["content/\nDirect LLM Pipeline\n(decompose → enrich → diagrams → quiz)"]
        IT["interactive_tutor/\nLangGraph Graph\n(5 nodes, conditional routing)"]
    end

    subgraph Core["Shared Core"]
        LF["LLMFactory\nanthropic | portkey | ollama"]
        MC["MCPClient\ntool discovery + dispatch"]
    end

    subgraph MCP["MCP Tool Servers"]
        DS[document_server]
        AS[assessment_server]
        SS[storage_server]
    end

    subgraph Storage
        DB[(SQLite)]
        VDB[(ChromaDB\nall-MiniLM-L6-v2)]
    end

    UP -->|"_run_pipeline()"| CF
    TUTOR -->|"graph.invoke()"| IT
    LIB & LEARN & QUIZ & RES --> DB

    CF --> MC & LF
    IT --> MC & LF
    MC --> DS & AS & SS
    SS --> DB & VDB
    DS --> DB
```

---

## 2. LLM Client — Factory & Adapters

All LLM access goes through a single factory. Callers pass Anthropic-format tool schemas; adapters translate internally.

```mermaid
---
title: LLM Client Class Hierarchy
---
classDiagram
    class BaseLLMClient {
        <<abstract>>
        +generate(prompt, system, tool_schema, context_blocks) str | dict
        +make_context_blocks(text) list
    }
    class AnthropicAdapter {
        +generate(...)
        +make_context_blocks(text) cached_blocks
    }
    class PortkeyAdapter {
        +generate(...)
        +make_context_blocks(text) cached_blocks
    }
    class OllamaAdapter {
        +generate(...)
        -_translate_tool_schema(schema) dict
    }
    class LLMFactory {
        +create(provider, **kwargs)$ BaseLLMClient
    }

    BaseLLMClient <|-- AnthropicAdapter
    BaseLLMClient <|-- PortkeyAdapter
    BaseLLMClient <|-- OllamaAdapter
    LLMFactory ..> BaseLLMClient : creates

    note for OllamaAdapter "Translates Anthropic tool schema\nto OpenAI function format.\nContext blocks degraded to\nplain text prefix (no caching)."
```

---

## 3. Content Pipeline — Direct LLM Calls

A linear pipeline where each step makes a single LLM call with a typed tool schema, ensuring deterministic structured output. Total cost: **3N + 2 LLM calls** for N topics.

```mermaid
---
title: Content Pipeline — Direct LLM Calls
---
flowchart LR
    PDF([PDF\nupload]) --> PARSE

    subgraph Pipeline["content/  —  Direct LLM Pipeline"]
        PARSE["Parse PDF\n\npdf_parser.py\nExtract sections with\nheading-aware splitting"]

        DECOMPOSE["Decompose\n\ntopic_decomposer.py\n1 LLM call\nIdentify learning topics"]

        ENRICH["Enrich Topics\n\ncontent_enricher.py\ndiagram_generator.py\ninline_question_gen.py\n3 LLM calls per topic"]

        QUIZ["Quiz Bank\n\nquestion_bank.py\n1 LLM call\n20-50 questions"]
    end

    PARSE --> DECOMPOSE --> ENRICH --> QUIZ

    QUIZ --> OUT([LearningModule\nstored in SQLite])
```

**Pipeline step details:**

| Step | Module | LLM calls | Output |
|---|---|---|---|
| Parse | `pdf_parser.py` | 0 | `Document` with `list[Section]` |
| Decompose | `topic_decomposer.py` | 1 | `list[Topic]` |
| Enrich (per topic) | `content_enricher.py` | 1 | `EnrichedTopic` with Markdown content |
| Diagrams (per topic) | `diagram_generator.py` | 1 | `list[Diagram]` (Mermaid) |
| Inline questions (per topic) | `inline_question_gen.py` | 1 | `list[Question]` (SCQ/MCQ) |
| Quiz bank | `question_bank.py` | 1 | `QuestionBank` |

---

## 4. LangGraph Interactive Tutor

Five node functions connected by a conditional router. The graph is the single source of truth for the tutoring session — every decision is made by inspecting `GraphState`.

### Graph State

```python
class GraphState(TypedDict):
    current_concept: str           # topic currently being taught
    concept_content: str           # enriched content from ChromaDB
    current_question: dict | None  # active question
    attempts: int                  # attempts on current concept (reset per concept)
    concept_mastered: bool         # set by evaluate_response
    mastered_concepts: list[str]   # accumulates across session
    chat_history: Annotated[list, add_messages]
    user_id: str
    module_id: str
```

### Graph Flow

```mermaid
---
title: LangGraph Interactive Tutor — State Machine
---
flowchart TD
    START([START]) --> PC

    PC["present_concept\n\nLoad concept content from ChromaDB\nDeliver explanation to student"]

    PC --> AQ

    AQ["ask_question\n\nGenerate targeted question\nassessing the current concept"]

    AQ --> WAIT([Wait for student answer])
    WAIT --> ER

    ER["evaluate_response\n\nLLM analyses answer\nChecks for specific misconceptions\nSets concept_mastered flag"]

    ER --> ROUTER{Conditional\nRouter}

    ROUTER -->|"concept_mastered\n== True"| NEXT{More\nconcepts?}
    NEXT -->|Yes| PC
    NEXT -->|No| DONE

    ROUTER -->|"attempts < 3\n&& not mastered"| PH

    PH["provide_hint\n\nTailor hint to student's\nspecific error"]

    PH --> AQ

    ROUTER -->|"attempts >= 3\n&& not mastered"| SF

    SF["simplify_foundations\n\nBreak concept into\nsimpler building blocks\nRe-teach from basics"]

    SF --> AQ

    DONE["session_complete\n\nSummarise mastery\nPersist to topic_mastery table"]
    DONE --> END([END])

```

### Router Logic

```
after evaluate_response:
    if concept_mastered:
        → next concept (or session_complete if all done)
    elif attempts < 3:
        → provide_hint → ask_question (retry)
    else:
        → simplify_foundations → ask_question (fresh approach)
```

---

## 5. MCP Tool Servers

Three standalone MCP servers. All backend orchestration (content pipeline, LangGraph nodes) accesses tools exclusively through `MCPClient` — no direct imports of `chromadb`, `fitz`, etc. outside the servers.

```mermaid
---
title: MCP Tool Servers and Dependencies
---
flowchart LR
    subgraph Callers["Backend Orchestration"]
        CF[content/\npipeline steps]
        IT[interactive_tutor/\nnodes]
    end

    MC["MCPClient"]

    subgraph document_server
        T1[extract_text_from_pdf]
        T2[parse_images]
    end

    subgraph assessment_server
        T3[validate_json_schema]
        T4[evaluate_taxonomy]
    end

    subgraph storage_server
        T5[upsert_to_vector_db]
        T6[save_module_to_db]
        T7[query_vector_db]
    end

    CF & IT --> MC
    MC --> document_server & assessment_server & storage_server

    document_server --> PyMuPDF[PyMuPDF]
    storage_server --> SQLite[(SQLite)]
    storage_server --> ChromaDB[(ChromaDB)]
```

---

## 6. Frontend Navigation

No admin/user separation. Any user can upload a PDF to generate a module, browse the library, learn, or enter the adaptive tutor.

```mermaid
---
title: Streamlit Page Navigation
---
stateDiagram-v2
    [*] --> upload

    upload --> module_library : Module generated

    module_library --> learn : Select module
    module_library --> upload : Generate new

    learn --> quiz : Take Quiz
    learn --> tutor_room : Start Tutor

    quiz --> results : Submit answers

    results --> quiz : Retake
    results --> module_library : Back to Library

    tutor_room --> module_library : End Session
```

---

## 7. Database Schema

```mermaid
---
title: SQLite Schema
---
erDiagram
    users {
        TEXT user_id PK
        TEXT username UK
        TEXT created_at
    }

    modules {
        TEXT module_id PK
        TEXT title
        TEXT source_filename
        TEXT module_json
        TEXT question_bank_json
        TEXT created_by FK
        TEXT created_at
    }

    quiz_attempts {
        TEXT attempt_id PK
        TEXT quiz_id
        TEXT module_id FK
        TEXT user_id FK
        TEXT difficulty
        INTEGER score
        INTEGER total
        REAL percentage
        TEXT completed_at
        TEXT answers_json
    }

    topic_mastery {
        TEXT user_id FK
        TEXT module_id FK
        TEXT topic_id
        INTEGER mastered
        TEXT difficulty
        INTEGER attempts
        TEXT last_updated
    }

    users ||--o{ modules : creates
    users ||--o{ quiz_attempts : attempts
    modules ||--o{ quiz_attempts : tested_on
    users ||--o{ topic_mastery : tracks
    modules ||--o{ topic_mastery : covers
```

---

## 8. Data Flow — End to End

Two independent paths through the system: batch generation (direct LLM pipeline) and live tutoring (LangGraph).

```mermaid
---
title: Two Data Paths
---
flowchart TD
    subgraph GenerationPath["Path 1: Module Generation (batch)"]
        direction LR
        PDF([PDF]) --> PARSE2[Parse\nPDF]
        PARSE2 --> DECOMP2[Decompose\nTopics]
        DECOMP2 --> ENRICH2[Enrich +\nDiagrams +\nQuestions]
        ENRICH2 --> DB2[(SQLite)]
    end

    subgraph TutoringPath["Path 2: Adaptive Tutoring (live)"]
        direction LR
        USER([Student]) --> PC2[present\nconcept]
        PC2 --> AQ2[ask\nquestion]
        AQ2 --> ER2[evaluate\nresponse]
        ER2 --> BRANCH2{mastered?}
        BRANCH2 -->|No| PH2[hint /\nsimplify]
        PH2 --> AQ2
        BRANCH2 -->|Yes| NEXT2[next concept]
    end

    DB2 -->|"load module +\nsemantic search"| PC2
```
