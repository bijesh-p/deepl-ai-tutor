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
        CF["content_factory/\nCrewAI Crew\n(3 agents, sequential)"]
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

    UP -->|"run_pipeline()"| CF
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

## 3. CrewAI Content Factory

Three agents run sequentially. Each agent's output is the next agent's input. Agents call MCP tool servers for document extraction, assessment validation, and storage.

```mermaid
---
title: CrewAI Content Factory — Agent Pipeline
---
flowchart LR
    PDF([PDF\nupload]) --> IA

    subgraph Crew["content_factory  —  Process.sequential"]
        IA["Information Architect\n\nExtract text via document_server\nDecompose into learning topics\nStructure topic hierarchy"]

        AD["Assessment Designer\n\nGenerate inline questions per topic\nBuild quiz question bank\nTag difficulty + Bloom's taxonomy\nvia assessment_server"]

        FS["Formatting Specialist\n\nGenerate Mermaid diagrams\nFormat content as learner-friendly Markdown\nValidate output schema\nPersist via storage_server"]
    end

    IA --> AD --> FS

    FS --> OUT([LearningModule\nstored in SQLite + ChromaDB])
```

**MCP tool usage by agent:**

| Agent | MCP server | Tools called |
|---|---|---|
| Information Architect | `document_server` | `extract_text_from_pdf`, `parse_images` |
| Assessment Designer | `assessment_server` | `evaluate_taxonomy` |
| Formatting Specialist | `storage_server` | `upsert_to_vector_db`, `save_module_to_db` |

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

Three standalone MCP servers. All backend orchestration (CrewAI agents, LangGraph nodes) accesses tools exclusively through `MCPClient` — no direct imports of `chromadb`, `fitz`, etc. outside the servers.

```mermaid
---
title: MCP Tool Servers and Dependencies
---
flowchart LR
    subgraph Callers["Backend Orchestration"]
        CF[content_factory\nagents]
        IT[interactive_tutor\nnodes]
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

Two independent paths through the system: batch generation (CrewAI) and live tutoring (LangGraph).

```mermaid
---
title: Two Data Paths
---
flowchart TD
    subgraph GenerationPath["Path 1: Module Generation (batch)"]
        direction LR
        PDF([PDF]) --> IA2[Information\nArchitect]
        IA2 --> AD2[Assessment\nDesigner]
        AD2 --> FS2[Formatting\nSpecialist]
        FS2 --> DB2[(SQLite +\nChromaDB)]
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
