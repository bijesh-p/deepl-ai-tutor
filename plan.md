# plan.md — AI Tutor Implementation

> **Goal:** Deliver a fully working AI Tutor with role-based access (Admin generates modules, Users consume them) and a persistent module library.
> **Spec:** SPEC.md v0.3
> **Last updated:** 2026-06-03

---

## Status of Original Phases (Phases 1–9) ✅ COMPLETE

All nine original phases are committed to `main`. The application is fully functional for the single-user PDF→LLM→Quiz flow.

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Project setup, dependencies, folder skeleton | ✅ Done |
| 2 | Data models across all five work streams | ✅ Done |
| 3 | PDF parser with 4-page cap | ✅ Done |
| 4 | Anthropic LLM client + topic decomposer | ✅ Done |
| 5 | Content enricher, diagram generator, inline questions | ✅ Done |
| 6 | Quiz engine — question bank, assembler, evaluator | ✅ Done |
| 7 | SQLite persistence and analytics | ✅ Done |
| 8 | Streamlit frontend — upload, learn, quiz, results | ✅ Done |
| 9 | Integration smoke test, README, references | ✅ Done |

---

## New Work — v0.3 Role-Based Access + Module Library

### What is changing

| Area | Current behaviour | New behaviour |
|------|------------------|---------------|
| Who uploads | Any user | Admin only (password-protected) |
| Who generates modules | Any user triggers LLM | Admin only; LLM runs once |
| Module persistence | Title + question_bank_json stored | Full LearningModule JSON stored |
| User entry point | Upload page | Module Library (browse + select) |
| Login | Username text box | Role-aware login (admin gets password prompt) |
| New pages | — | `login_page`, `admin_upload_page`, `module_library_page` |

---

## Phase 10 — DB Schema + Persistence Upgrade

**Goal:** Extend the SQLite schema to store the full LearningModule JSON, add a `role` column to users, and add `created_by` + `module_json` to modules. Update persistence functions to match.

**Files modified:**
- `analytics/db.py`
  - `users` table: add `role TEXT NOT NULL DEFAULT 'user'`
  - `modules` table: add `module_json TEXT NOT NULL` and `created_by TEXT NOT NULL`
  - Drop and recreate schema (dev DB only — add `DROP TABLE IF EXISTS` guards for clean rebuild)
- `analytics/persistence.py`
  - `save_user(username, role='user', db=None) -> str` — add role param
  - `save_module(module, question_bank_json, module_json, created_by, db=None)` — add module_json + created_by params
  - New: `load_module(module_id, db=None) -> dict` — returns raw JSON strings for both module and bank
  - New: `list_modules(db=None) -> list[dict]` — returns `[{module_id, title, source_filename, created_at}]` for the library page
- `tests/test_analytics/test_persistence.py` — update tests for new schema and new functions

**Open questions:** None — decisions made in SPEC.md v0.3.

**Commit message:** `[Phase 10] DB schema v2: role-based users, module_json persistence, list/load APIs`

---

## Phase 11 — LearningModule JSON Serialization

**Goal:** Add `to_json()` and `from_dict()` to `LearningModule` (and its nested types) so modules can be stored to and loaded from the database without re-running the LLM.

**Files modified:**
- `content/models.py`
  - Add `to_json() -> str` to `LearningModule` using `dataclasses.asdict()` + `json.dumps()`
  - Add `LearningModule.from_dict(data: dict) -> LearningModule` — reconstructs full nested dataclass tree from a plain dict
  - All nested types (`EnrichedTopic`, `Topic`, `Diagram`, `Question`) are reconstructed inside `from_dict`

**Design note:** `from_dict` rebuilds the full object graph:
```
dict → LearningModule
         └── list[EnrichedTopic]
               ├── topic: Topic
               ├── diagrams: list[Diagram]
               └── inline_questions: list[Question]
```

**Files modified:**
- `tests/test_content/` — add round-trip test: `LearningModule.from_dict(module.to_json())` gives equal object

**Commit message:** `[Phase 11] LearningModule to_json/from_dict for DB round-trip`

---

## Phase 12 — Login Page

**Goal:** Single login page that routes admins (password-matched) to the admin upload page and regular users (username-only) to the module library.

**Files created:**
- `frontend/login_page.py`
  - `render_login_page()`
  - Username text input always shown
  - Password input shown when `AI_TUTOR_ADMIN_USERNAME` matches entered username
  - On submit:
    - Admin path: verify password against `AI_TUTOR_ADMIN_PASSWORD` env var; on success set `role=admin`, save admin user to DB, navigate to `admin_upload`
    - User path: no password check; save user to DB (role=user), navigate to `module_library`
  - Shows an error on wrong admin password without revealing which field is wrong

**Files modified:**
- `.env.example` — add `AI_TUTOR_ADMIN_USERNAME=admin` and `AI_TUTOR_ADMIN_PASSWORD=`

**Commit message:** `[Phase 12] Login page with admin/user role routing`

---

## Phase 13 — Admin Upload Page

**Goal:** Dedicated admin-only page for uploading PDFs and generating learning modules. Saves the full module to the DB on completion. Refactored from the existing `upload_page.py`.

**Files created:**
- `frontend/admin_upload_page.py`
  - `render_admin_upload_page()`
  - Guard: if `st.session_state["role"] != "admin"` → redirect to login
  - PDF file uploader
  - "Generate Learning Module" button
  - Live `st.status()` log panel (6 steps, same as current upload_page.py)
  - On completion: calls `save_module(module, question_bank_json=..., module_json=module.to_json(), created_by=user_id)`
  - Success message with module title + "Go to Module Library" button
  - Does **not** navigate to learn page (admin generates, users learn)

**Files modified:**
- `frontend/upload_page.py` — kept as-is for reference but no longer used by the router

**Commit message:** `[Phase 13] Admin upload page with module persistence`

---

## Phase 14 — Module Library Page

**Goal:** A browsable list of all published modules, available to both admins and users. Clicking "Learn" loads the full module from the DB (no LLM call) and navigates to the module viewer.

**Files created:**
- `frontend/module_library_page.py`
  - `render_module_library_page()`
  - Calls `list_modules()` to get all available modules from DB
  - Displays as a table: Title | Source File | Created | Actions
  - "Learn" button per row:
    - Calls `load_module(module_id)` to get stored JSON strings
    - Deserialises: `LearningModule.from_dict(json.loads(module_json))`
    - Deserialises: `QuestionBank` from `question_bank_json`
    - Sets `st.session_state["module"]`, `st.session_state["bank"]`, navigates to `learn`
  - Empty state message when no modules exist yet ("No modules available — ask an admin to generate one")
  - Admin additionally sees a "Delete" button per row (calls `delete_module(module_id)`)

**Files modified:**
- `analytics/persistence.py` — add `delete_module(module_id, db=None)` function

**Commit message:** `[Phase 14] Module library page — browse, select, and load published modules`

---

## Phase 15 — App Router + Cleanup + Docs

**Goal:** Wire all new pages into `app.py`. Update the navigation state machine. Update README and `.env.example`.

**Files modified:**
- `app.py`
  - New page states: `login`, `admin_upload`, `module_library`, `learn`, `quiz`, `results`
  - Entry point: if no session, route to `login`
  - Guard: `admin_upload` requires `role == admin`; redirect to `login` otherwise
  - "Back to Library" button on results page sets page to `module_library`
  - Remove direct routing to old `upload` page
- `frontend/results_page.py`
  - Replace "Upload New Document" button with "Back to Module Library" button
- `README.md`
  - Update Quick Start section with admin/user flow
  - Add environment variables for admin credentials
  - Update application flow diagram
- `.env.example`
  - Add `AI_TUTOR_ADMIN_USERNAME=admin` and `AI_TUTOR_ADMIN_PASSWORD=changeme`

**Commit message:** `[Phase 15] App router v2: login → library flow, README and env updates`

---

## Implementation Order (dependency graph)

```
Phases 1–9 (complete)
       │
       ├── Phase 10  (DB schema + persistence)
       │       │
       │       ├── Phase 11  (LearningModule serialization)
       │       │       │
       │       │       ├── Phase 12  (Login page)
       │       │       │
       │       │       ├── Phase 13  (Admin upload page)
       │       │       │
       │       │       └── Phase 14  (Module library page)
       │       │               │
       │       └───────────────┴── Phase 15  (App router + docs)
```

Phases 12, 13, 14 can be developed in parallel once Phases 10 and 11 are done.

---

## Files Summary

| Phase | Files Created | Files Modified |
|-------|--------------|----------------|
| 10 | — | `analytics/db.py`, `analytics/persistence.py`, `tests/test_analytics/test_persistence.py` |
| 11 | — | `content/models.py`, `tests/test_content/` |
| 12 | `frontend/login_page.py` | `.env.example` |
| 13 | `frontend/admin_upload_page.py` | — |
| 14 | `frontend/module_library_page.py` | `analytics/persistence.py` (delete_module) |
| 15 | — | `app.py`, `frontend/results_page.py`, `README.md`, `.env.example` |
| **Total** | **3 new files** | **8 modified files** |
