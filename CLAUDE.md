# CLAUDE.md — AI Tutor Project

## Project Overview

Problem:

Static documents like PowerPoint and PDFs lead to passive learning and poor knowledge retention. Manually creating and updating interactive content is time-consuming, expensive, and difficult to scale.

Proposed Solution:

AI Tutor is an intelligent web application that transforms static documentation (PDFs, PowerPoint, Word, and WebVTT transcripts) into dynamic, interactive learning modules. Uploaded content is decomposed into sub-topics with diagrams, audio narration, and inline questions, then served either as a self-paced module with a Bloom's-taxonomy-leveled quiz, or through a LangGraph-driven adaptive tutor that diagnoses the learner, adapts depth in real time, and tracks mastery across sessions. The platform also includes an admin-curated shared module library, a dark-mode UI, observability (tracing + LLM-judge evals), centralized input/output guardrails on every LLM call, and an experimental per-module knowledge graph that guides hints and concept ordering beyond plain vector search.

All authoritative requirements live in **SPEC.md**.

---

## Workflow Rules

### 1. Always update SPEC.md first

Before writing any code for a new feature or change:
1. Update `SPEC.md` with the relevant section changes, new decisions, or resolved open questions.
2. If a requirement is ambiguous or contradicts existing spec, **ask the user to confirm** — never assume.
3. Only proceed to implementation after the spec reflects the intended design.

### 2. Create plan.md before implementing

For every non-trivial task (new module, feature, or significant change):
1. Create or update `plan.md` at the repo root with:
   - **Goal** — what will be built or changed.
   - **Phases** — numbered steps, each scoped to a single commit.
   - **Files affected** — list files to be created or modified.
   - **Open questions** — anything that needs user confirmation before proceeding.
2. Present the plan to the user and wait for approval before writing code.
3. Keep `plan.md` updated as phases complete.

### 3. Commit after each phase

After each phase in `plan.md` is complete:
- **Always use the `/git-commit` skill** — never run `git commit` directly. Invoke it with the Skill tool (`skill: "git-commit"`).
- Commit message format: `[Phase N] <short description>` (e.g., `[Phase 1] Add data pipeline`).
- Do not bundle multiple phases into one commit.
- The skill handles staging, commit message formatting, and any pre-commit hooks.
- **Committing to `main` is explicitly allowed** for this repo — this is an assignment repository with a single-branch workflow.

### 4. Update pyproject.toml for new dependencies

Whenever a new library is identified (during planning or implementation):
1. Add it to `pyproject.toml` under `[project] dependencies`.
2. Install with `uv add <package>` so `uv.lock` stays in sync.
3. Do not use `pip install` directly — always go through `uv`.

### 5. Update README.md after each phase

After committing a phase:
- Update `README.md` with any new setup steps, CLI usage, or changed entry points.
- The README must always reflect the current runnable state of the repo.

### 6. Maintain references.md

- Keep `references.md` at the repo root with annotated links to documentation, papers, and tutorials for every key technology used.
- Add entries when a new library or technique is introduced.
- Format: `## <Topic>` heading, then bullet list of `[Title](URL) — one-line explanation`.

---

## Python & Package Management

### Local PC (development, inference, visualization)
- **Runtime:** Python 3.14 (see `.python-version`).
- **Package manager:** [`uv`](https://docs.astral.sh/uv/) — use it for all local dependency and environment operations.
- **Running scripts:** `PYTHONPATH=. uv run python <script>.py` — the `PYTHONPATH=.` is required so subpackages (`utils`, `data`, `model`) resolve correctly from the project root.
- **Adding packages:** `uv add <package>` (updates `pyproject.toml` and `uv.lock`).
- **Removing packages:** `uv remove <package>`.
- **Sync environment:** `uv sync` after pulling changes that modify `pyproject.toml`.


---

## Spec-Driven Development Cycle

```
1. Read SPEC.md
       │
       ▼
2. Identify ambiguities → ask user to confirm
       │
       ▼
3. Update SPEC.md with resolved decisions
       │
       ▼
4. Write / update plan.md (phases + files)
       │
       ▼
5. Get user approval on plan.md
       │
       ▼
6. Implement phase N
       │
       ▼
7. uv add any new deps → update pyproject.toml
       │
       ▼
8. Update README.md
       │
       ▼
9. Update references.md with new tech/links
       │
       ▼
10. Commit via git-commit skill → [Phase N] message
       │
       └── repeat from step 6 for next phase
```

---

## Project Structure

See [ARCHITECTURE.md §1](ARCHITECTURE.md#1-directory-structure) for the current directory layout.

---

## Diagrams

Use Mermaid diagrams whenever a visual would aid understanding. This applies to:

- **Architecture / data flow** — system overviews, how modules connect
- **Sequence diagrams** — multi-step processes (e.g., upload → parse → generate → quiz flow)
- **Flowcharts** — decision trees, branching logic, error handling paths
- **Entity relationships** — database schemas, data model relationships
- **Class diagrams** — when documenting class hierarchies or interface contracts

### Rules

1. Prefer a Mermaid diagram over a plain-text ASCII diagram whenever the content is non-trivial.
2. Use the simplest diagram type that conveys the information — flowchart for flow, sequenceDiagram for interactions, erDiagram for schemas.
3. Always give diagrams a descriptive title using the `---\ntitle: ...\n---` frontmatter block.
4. Keep diagrams focused — one concept per diagram. Split complex diagrams into two smaller ones rather than producing an unreadable one.
5. In Markdown documents (README, SPEC, plan), embed diagrams in fenced code blocks with the `mermaid` language tag.

### Example

````markdown
```mermaid
---
title: AI Tutor Data Flow
---
flowchart LR
    Upload([User uploads PDF]) --> Ingest[Document Ingestion]
    Ingest --> Content[Content Generation]
    Content --> Quiz[Quiz Engine]
    Quiz --> Analytics[Analytics Layer]
    Analytics --> UI[Streamlit UI]
```
````

---
