# plan.md — AI Tutor Implementation Plan

> **Status:** Commit 1 pending
> **Last updated:** 2026-06-02

---

## Strategy

Ship working code as fast as possible. The shared data models are the only real dependency between streams — once those exist as JSON fixtures, every developer can work independently and in parallel without waiting for upstream streams to be implemented.

**No skeleton phase. No stubs. Everyone builds real logic from day one.**

---

## Commit 1 — Shared Models + Fixtures
**Owner:** One person (unblocks everyone else)
**Target:** < 1 hour

Create the shared dataclasses and sample JSON fixtures that all other streams use as stand-ins for upstream data.

**Files:**
```
ingestion/models.py          ← Document, Section, ExtractedImage, SourceType
content/models.py            ← Topic, Diagram, Question, EnrichedTopic, LearningModule
quiz/models.py               ← QuizQuestion, QuestionBank, Quiz, AnswerResult, QuizResult
analytics/models.py          ← ModuleStats
tests/fixtures/
    sample_document.json     ← hardcoded Document (3-4 sections, 1 image path)
    sample_module.json       ← hardcoded LearningModule (2 topics, 2 inline questions each)
    sample_bank.json         ← hardcoded QuestionBank (6 questions, 2 per difficulty)
    sample_result.json       ← hardcoded QuizResult (5/6, mixed correct/incorrect)
    sample_stats.json        ← hardcoded ModuleStats (min/max/avg/percentile)
.env.example                 ← all env vars with descriptions
```

All dataclasses are **complete** — include `to_json()` / `from_json()` serialization on each.  
Fixtures are **realistic** — enough detail for UI and tests to look credible.

**Commit message:** `[Commit 1] Shared data models and test fixtures`

---

## Commit 2 — Stream 1: PDF Ingestion
**Owner:** Person A (parallel with Commits 3, 4, 5)
**Depends on:** Commit 1

**Files:**
```
ingestion/__init__.py
ingestion/image_extractor.py
ingestion/pdf_parser.py
tests/test_ingestion/test_pdf_parser.py
tests/fixtures/sample.pdf    ← small real PDF for testing
```

**PPTX and DOCX parsers are not created yet** — add them in a later commit when ready.

**New deps:**
```
uv add pymupdf
```

**What to implement:**

`image_extractor.py` — `extract_images(page, output_dir, doc_id, page_num) -> list[ExtractedImage]`
- Extract images from a PyMuPDF page object
- Save as PNG to `data/uploads/<doc_id>/images/`
- Return list of `ExtractedImage` with path + source location

`pdf_parser.py` — `parse_pdf(file_path: str) -> Document`
- Open with `fitz.open(file_path)`
- Detect headings via font-size heuristic (largest font on a page = section heading)
- Group text blocks under headings → one `Section` per heading group
- Call `extract_images()` per page
- Return `Document` with `source_type=SourceType.PDF`

**Tests:** Assert on a real sample PDF — correct section count, non-empty body text, image paths exist on disk.

**Commit message:** `[Commit 2] Stream 1 — PDF parser with image extraction`

---

## Commit 3 — Stream 2: LLM Client + Content Generation
**Owner:** Person B (parallel with Commits 2, 4, 5)
**Depends on:** Commit 1 (uses `sample_document.json` as input fixture)

**Files:**
```
content/__init__.py
content/llm_client.py
content/topic_decomposer.py
content/content_enricher.py
content/diagram_generator.py
content/inline_question_gen.py
tests/test_content/test_llm_client.py
tests/test_content/test_pipeline.py
```

**New deps:**
```
uv add anthropic portkey-ai
```

**What to implement:**

`llm_client.py`:
```python
class Provider(Enum):
    ANTHROPIC = "anthropic"   # Direct via anthropic SDK
    PORTKEY   = "portkey"     # Via Portkey gateway

class LLMClient:
    def __init__(self, provider: Provider, api_key: str, model: str,
                 portkey_virtual_key: str | None = None): ...
    def generate(self, prompt: str, system: str | None = None,
                 response_schema: dict | None = None) -> str | dict: ...
```
- ANTHROPIC: `anthropic.Anthropic(api_key=...).messages.create(...)`
- PORTKEY: `portkey_ai.Portkey(api_key=portkey_api_key, virtual_key=...).messages.create(...)`
- Both return the same interface — caller never sees the difference
- Provider selected via `AI_TUTOR_LLM_PROVIDER` env var

`topic_decomposer.py` — `decompose(doc: Document, llm: LLMClient) -> list[Topic]`
- Send all section titles + bodies to LLM in one prompt
- Ask for structured JSON: list of topics, each with title, summary, source section IDs

`content_enricher.py` — `enrich(topic: Topic, doc: Document, llm: LLMClient) -> EnrichedTopic`
- Send topic source sections to LLM
- Ask for: learner-friendly rewrite (Markdown), key takeaways list

`diagram_generator.py` — `generate_diagrams(topic: EnrichedTopic, llm: LLMClient) -> list[Diagram]`
- Ask LLM if a diagram adds value; if yes, return Mermaid code
- Return empty list if LLM says no diagram needed

`inline_question_gen.py` — `generate_inline_questions(topic: EnrichedTopic, llm: LLMClient) -> list[Question]`
- Ask LLM for 2-3 MCQ/SCQ with options, correct answers, explanations
- Return as `list[Question]`

**Tests:** Use a `MockLLMClient` that returns hardcoded JSON matching the schema — no real API calls needed.

**Commit message:** `[Commit 3] Stream 2 — LLM client (Claude direct + Portkey) and content pipeline`

---

## Commit 4 — Streams 3 + 4: Quiz Engine + Analytics
**Owner:** Person C (parallel with Commits 2, 3, 5)
**Depends on:** Commit 1 (uses `sample_module.json`, `sample_result.json` as fixtures)

**Files:**
```
quiz/__init__.py
quiz/question_bank.py
quiz/difficulty.py
quiz/assembler.py
quiz/evaluator.py
analytics/__init__.py
analytics/db.py
analytics/persistence.py
analytics/stats.py
tests/test_quiz/test_assembler.py
tests/test_quiz/test_evaluator.py
tests/test_analytics/test_persistence.py
tests/test_analytics/test_stats.py
```

**No new deps** (uses `sqlite3` stdlib + shared `LLMClient` from Commit 3).

**What to implement:**

`question_bank.py` — `generate_question_bank(module: LearningModule, llm: LLMClient) -> QuestionBank`
- One LLM call per topic: generate 4-6 questions, each tagged easy/medium/hard in the same response
- Aggregate into `QuestionBank`

`difficulty.py` — difficulty is assigned during generation (no separate step needed)
- Expose a helper `validate_difficulty(tag: str) -> str` that normalises to `easy|medium|hard`

`assembler.py` — `assemble_quiz(bank: QuestionBank, difficulty: str, num_questions: int = 10) -> Quiz`
- Filter by difficulty; if insufficient, pull from adjacent levels
- Shuffle with `random.sample`; return `Quiz`

`evaluator.py` — `evaluate(quiz: Quiz, user_answers: dict[str, list[int]]) -> QuizResult`
- Single-choice: exact match on one index
- Multiple-choice: all correct indices must be selected, no extras

`db.py` — `get_db(path: str | None = None) -> sqlite3.Connection`
- Auto-creates tables on first call (schema from SPEC §5.2.1)
- `path=":memory:"` for tests

`persistence.py` — `save_user`, `save_attempt`, `get_user_attempts`, `save_module`

`stats.py` — `get_module_stats(module_id: str, user_id: str) -> ModuleStats`
- Percentile = (attempts with percentage ≤ user score) / total × 100
- Edge case: single attempt → percentile = 100.0

**Tests:** In-memory SQLite for all analytics tests. Hardcoded `QuestionBank` fixture for assembler/evaluator tests.

**Commit message:** `[Commit 4] Streams 3+4 — Quiz engine and analytics with SQLite`

---

## Commit 5 — Stream 5: Streamlit Frontend
**Owner:** Person D (parallel with Commits 2, 3, 4)
**Depends on:** Commit 1 (uses fixture JSONs as mock data; integrates real backends after Commits 2-4 merge)

**Files:**
```
app.py
frontend/__init__.py
frontend/upload_page.py
frontend/module_viewer.py
frontend/quiz_page.py
frontend/results_page.py
```

**New deps:**
```
uv add streamlit plotly
```

**What to implement:**

`app.py` — navigation via `st.session_state["page"]`:
```
"upload" → "learn" → "quiz" → "results"
           ↑                      |
           └──── retake ──────────┘
```

`upload_page.py` — `render_upload_page()`
- `st.file_uploader` accepting `.pdf` only (PPTX/DOCX added later)
- Username text input (no auth)
- "Generate Module" button → calls ingestion + content pipeline with `st.status()` progress
- On success: save to `st.session_state`, navigate to `"learn"`

`module_viewer.py` — `render_module_viewer(module: LearningModule)`
- Sidebar: topic list as navigation links
- Per topic: Markdown content, key takeaways in a callout box, Mermaid code in `st.code()`, inline questions with `st.radio` / `st.multiselect` + immediate feedback

`quiz_page.py` — `render_quiz_page(bank: QuestionBank)`
- Difficulty radio at top
- Numbered questions; `st.radio` for single-choice, `st.multiselect` for multiple-choice
- "Submit Quiz" button → calls `assembler` + `evaluator` → navigate to `"results"`

`results_page.py` — `render_results_page(result: QuizResult, stats: ModuleStats)`
- Score headline, per-question accordion (correct/incorrect + explanation)
- Plotly grouped bar chart: user vs min/avg/max
- Percentile callout
- "Retake" and "Upload New" buttons

**During development:** load fixtures from `tests/fixtures/*.json` directly — swap for real calls once Commits 2-4 merge.

**Commit message:** `[Commit 5] Stream 5 — Streamlit UI (upload, learn, quiz, results)`

---

## Commit 6 — Integration + Smoke Test
**Owner:** Whole team
**Depends on:** Commits 2-5

Wire up `app.py` to call real implementations instead of fixtures. Run the full flow end-to-end with a real PDF.

**Checklist (from SPEC §8.2):**
- [ ] Upload a real PDF → `Document` created with correct sections + images
- [ ] `Document` → `LearningModule` with topics, diagrams, inline questions
- [ ] `LearningModule` → `QuestionBank` with 20+ questions at all difficulties
- [ ] Quiz assembled + evaluated correctly
- [ ] `QuizResult` saved to DB; analytics chart shows correct min/max/avg
- [ ] Retake produces different question order
- [ ] Full flow: Upload → Learn → Quiz → Results → Retake

Update `README.md` and `references.md`.

**Commit message:** `[Commit 6] Integration — end-to-end PDF flow verified`

---

## Dependency Summary

| Package      | Added by   | Command             |
| ------------ | ---------- | ------------------- |
| `pymupdf`    | Commit 2   | `uv add pymupdf`    |
| `anthropic`  | Commit 3   | `uv add anthropic`  |
| `portkey-ai` | Commit 3   | `uv add portkey-ai` |
| `streamlit`  | Commit 5   | `uv add streamlit`  |
| `plotly`     | Commit 5   | `uv add plotly`     |

## Environment Variables

| Variable                       | Purpose                             | Default            |
| ------------------------------ | ----------------------------------- | ------------------ |
| `AI_TUTOR_LLM_PROVIDER`        | `anthropic` or `portkey`           | `anthropic`        |
| `AI_TUTOR_LLM_API_KEY`         | Anthropic API key                  | (required)         |
| `AI_TUTOR_LLM_MODEL`           | Claude model name                  | `claude-opus-4-8`  |
| `AI_TUTOR_PORTKEY_API_KEY`     | Portkey API key                    | (if portkey)       |
| `AI_TUTOR_PORTKEY_VIRTUAL_KEY` | Portkey virtual key for Claude     | (if portkey)       |
| `AI_TUTOR_DB_PATH`             | SQLite path                        | `data/ai_tutor.db` |
| `AI_TUTOR_UPLOAD_DIR`          | Upload directory                   | `data/uploads`     |
| `AI_TUTOR_MAX_FILE_MB`         | Max file size MB                   | `50`               |

## Open Questions

- [ ] Persist `QuestionBank` to DB (avoid regenerating on retake) or regenerate fresh each time?
- [ ] Mermaid: render via `streamlit-mermaid` package or show as code block for MVP?
- [ ] Module library across sessions (persist `LearningModule` JSON) or fresh each upload?
