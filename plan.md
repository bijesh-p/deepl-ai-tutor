# plan.md — AI Tutor Implementation

> **Goal:** Deliver a fully working AI Tutor with just-in-time content delivery and adaptive tutoring.
> **Spec:** SPEC.md v0.6
> **Last updated:** 2026-06-14

---

## Status of Original Phases (Phases 1–16) ✅ COMPLETE

All original phases are committed. The application is fully functional for the PDF → LLM → Quiz flow with role-based access and module library.

---

## Phase 1–7 — Codebase Restructure ✅ COMPLETE

Migrated from flat structure to layered `backend/` + `frontend/` + `mcp_servers/` architecture.

## Phase 8 — Remove CrewAI ✅ COMPLETE

Removed all CrewAI references from code, docs, and dependencies.

## Phase 9 — Background Pipeline + Progress Tracking ✅ COMPLETE

Moved pipeline to background daemon thread. Added `@st.fragment(run_every=2)` status poller, abort support, and tab-switch resilience.

## Phase 10 — Just-in-Time Content Delivery ✅ COMPLETE

Restructured the pipeline for incremental delivery:

| Sub-phase | Description | Files Modified |
|-----------|-------------|----------------|
| 1 | Incremental pipeline — publish each enriched topic as it completes, redirect after topic 1 | `frontend/upload_page.py` |
| 2 | Partial module viewer with `@st.fragment(run_every=3)` live polling | `frontend/module_viewer.py` |
| 3 | Tutor room handles not-yet-enriched topics gracefully | `frontend/tutor_room.py` |
| 4 | Deferred quiz — button disabled until quiz bank ready | `frontend/module_viewer.py` |
| 5 | Save completed module to DB after quiz generation | `frontend/upload_page.py` |
| 6 | Updated global banner for new pipeline states | `app.py` |

**Key change:** Users start learning within ~30 seconds (after topic 1 enrichment) instead of waiting 2-5 minutes for full generation. Remaining topics and quiz generate in the background.
