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

## Phase 26 — Diagram-First Slide Generation

**Goal:** Flip the slide creation order — generate the visual anchor (diagram or bullet fallback) first, then write the explanation text anchored to it. Every slide explanation must reference only what's in the anchor.

**Phases:**

### Phase 26a — `diagram_generator.py`: accept raw source text (not EnrichedTopic)

Currently `generate_diagrams(enriched, llm)` requires a fully enriched topic.
Change signature to `generate_slide_anchor(source_text, topic, llm) -> SlideAnchor`.

- Input: raw source text + `Topic` (title + summary)
- Attempts Mermaid diagram generation
- If diagram is empty/invalid → calls `_generate_key_bullets(source_text, topic, llm)`
  to produce 4-6 bulleted key points
- Returns `SlideAnchor(diagram: Diagram | None, bullets: list[str])`

**Files:** `backend/content/diagram_generator.py`

---

### Phase 26b — `content_enricher.py`: accept SlideAnchor as context

Change `enrich(topic, source_text, llm)` → `enrich(topic, source_text, anchor, llm)`.

- If `anchor.diagram`: system prompt instructs "walk through this diagram"
- If `anchor.bullets`: system prompt instructs "expand on these bullet points"
- The enricher must not introduce concepts not in the anchor

**Files:** `backend/content/content_enricher.py`

---

### Phase 26c — `sliding_pipeline._enrich_one`: reorder steps

New order:
1. `generate_slide_anchor(source_text, topic, llm)` — diagram or bullets
2. `enrich(topic, source_text, anchor, llm)` — text anchored to the visual
3. `generate_inline_questions(enriched, llm)` — questions from enriched content
4. `generate_audio(...)` — TTS narration

**Files:** `backend/content/sliding_pipeline.py`

---

### Phase 26d — Update tests

- `test_pipeline.py`: mock `generate_slide_anchor`; verify anchor is passed to `enrich`
- `test_topic_decomposer.py`: no change (tests `_assess` / `_make_topic`)
- Add `test_diagram_generator.py` tests for bullet fallback path

**Files:** `tests/test_content/test_pipeline.py`, `tests/test_content/test_diagram_generator.py`

---

**Files affected:**

| File | Change |
|---|---|
| `backend/content/diagram_generator.py` | New `generate_slide_anchor()` + bullet fallback |
| `backend/content/content_enricher.py` | Accept `SlideAnchor` as context |
| `backend/content/sliding_pipeline.py` | Reorder steps in `_enrich_one` |
| `tests/test_content/test_pipeline.py` | Update mocks for new order |
| `tests/test_content/test_diagram_generator.py` | New — test bullet fallback |

---

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
