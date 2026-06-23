# references.md — Annotated Technology References

## Document Parsing

- [PyMuPDF Documentation](https://pymupdf.readthedocs.io/) — Python bindings for MuPDF; used for PDF text extraction and TOC parsing in `backend/ingestion/pdf_parser.py`.
- [PyMuPDF GitHub](https://github.com/pymupdf/PyMuPDF) — Source and issue tracker.

## WebVTT Transcript Parsing

- [WebVTT Spec (W3C)](https://www.w3.org/TR/webvtt1/) — W3C standard for timed text tracks; defines the `.vtt` format parsed by `backend/ingestion/vtt_parser.py`.
- [WebVTT on MDN](https://developer.mozilla.org/en-US/docs/Web/API/WebVTT_API) — MDN reference for WebVTT cue formatting, voice tags (`<v>`), and timestamp syntax.

## LLM Integration

- [Anthropic Python SDK](https://github.com/anthropic/anthropic-sdk-python) — Official SDK used in `backend/core/llm_client/adapters/anthropic_adapter.py`.
- [Anthropic API Docs — Tool Use](https://docs.anthropic.com/en/docs/tool-use) — Structured output via tool-use; used for all LLM calls to get typed JSON responses.
- [Anthropic API Docs — Prompt Caching](https://docs.anthropic.com/en/docs/prompt-caching) — Cache control on system prompt and document blocks to reduce token costs.
- [Portkey AI](https://docs.portkey.ai/) — AI gateway for LLM routing; used in `backend/core/llm_client/adapters/portkey_adapter.py`.
- [Ollama](https://ollama.com/) — Local LLM runner with OpenAI-compatible endpoint; used in `backend/core/llm_client/adapters/ollama_adapter.py`.
- [OpenAI Python SDK](https://github.com/openai/openai-python) — Used for Ollama's OpenAI-compatible function calling interface.

## Adaptive Tutoring

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/) — State machine framework for building agent workflows; powers the 5-node interactive tutor in `backend/interactive_tutor/`.
- [LangGraph GitHub](https://github.com/langchain-ai/langgraph) — Source and issue tracker.
- [LangGraph Checkpoint SQLite](https://langchain-ai.github.io/langgraph/reference/checkpoints/) — SqliteSaver for persisting tutor session state.

## Assessment & Question Generation

- [Scaria et al., "Automated Educational Question Generation at Different Bloom's Skill Levels using Large Language Models: Strategies and Evaluation" (AIED 2024)](https://arxiv.org/abs/2408.04394) — informs the six-level (remember/understand/apply/analyze/evaluate/create) question generation used across `backend/quiz/question_bank.py`, inline questions, and the diagnostic/tutor-room prompts in `backend/interactive_tutor/graph.py`. Specifically uses the paper's PS2 prompting strategy (persona + chain-of-thought + inline skill-level definitions), which it found gave the best quality/skill-adherence balance; PS5's hardcoded few-shot examples measurably hurt both, so none were added.

## LLM Safety / Guardrails

- [OWASP Top 10 for LLM Applications — Prompt Injection](https://owasp.org/www-project-top-10-for-large-language-model-applications/) — informs the rule-based prompt-injection patterns in `backend/core/guardrails/rules.py` (instruction-override phrasing, fake role-marker tags, jailbreak keywords).
- [Anthropic — Tool Use](https://docs.anthropic.com/en/docs/tool-use) (same SDK feature as above) — the content-moderation and topic-relevance checks in `backend/core/guardrails/judge.py` reuse the existing tool-schema pattern to get a structured, parseable classification from an LLM-as-judge call against the real configured provider.

## Model Context Protocol (MCP)

- [MCP Specification](https://modelcontextprotocol.io/) — Protocol for LLM tool access; three MCP servers in `mcp_servers/`.
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) — Python SDK for building MCP servers and clients.

## Vector Store & Embeddings

- [ChromaDB Documentation](https://docs.trychroma.com/) — Embedding database for semantic search over document chunks in `mcp_servers/storage_server/`.
- [ChromaDB GitHub](https://github.com/chroma-core/chroma) — Source and issue tracker.
- [ChromaDB `DefaultEmbeddingFunction`](https://github.com/chroma-core/chroma/blob/main/chromadb/utils/embedding_functions/onnx_mini_lm_l6_v2.py) — ONNX export of `all-MiniLM-L6-v2`, run via `onnxruntime` instead of `sentence-transformers`/`torch`. Used in `_get_chroma_collection()` because `torch` has no wheel for Python 3.13 on Intel macOS (`macosx_x86_64`).
- [all-MiniLM-L6-v2 on HuggingFace](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) — Lightweight embedding model (384 dimensions, 22M params); same weights, ONNX runtime instead of PyTorch.

## Audio / Text-to-Speech

- [edge-tts](https://github.com/rany2/edge-tts) — Python library for Microsoft Edge's TTS API; used in `backend/content/audio_generator.py` for topic narration.

## LLM Observability and Evaluation

- [Arize Phoenix](https://arize.com/docs/phoenix/) — Local OTEL-native LLM trace server; receives spans at `http://localhost:6006/v1/traces`. Start with `uv run phoenix serve`.
- [openinference-instrumentation-anthropic](https://github.com/Arize-ai/openinference/tree/main/python/instrumentation/openinference-instrumentation-anthropic) — Auto-patches the Anthropic SDK to emit OTEL spans for every `messages.create()` call.
- [openinference-instrumentation-langchain](https://github.com/Arize-ai/openinference/tree/main/python/instrumentation/openinference-instrumentation-langchain) — Auto-patches LangGraph node execution to emit OTEL spans.
- [OpenTelemetry Python SDK](https://opentelemetry.io/docs/languages/python/) — OTEL tracer provider, batch span processor, OTLP HTTP exporter.
- [DeepEval](https://deepeval.com/docs/getting-started) — LLM evaluation framework; provides `AnswerRelevancyMetric`, `FaithfulnessMetric`, `GEval`; runs after each tutoring session in `backend/observability/eval_runner.py`.
- [LangSmith](https://docs.smith.langchain.com/) — Secondary trace destination for LangGraph; activated via `LANGCHAIN_TRACING_V2=true` env var (no new package required).

## Frontend

- [Streamlit Documentation](https://docs.streamlit.io/) — Python web framework powering all UI pages.
- [streamlit-mermaid](https://github.com/jhavens1566/streamlit-mermaid) — Streamlit component for rendering Mermaid diagrams. **Replaced** by a custom vendored renderer (`frontend/mermaid_render.py`) — its client-side render failures couldn't be caught by Python `try/except`, so diagram errors surfaced mermaid.js's raw syntax-error text with no fallback.
- [Mermaid Diagram Syntax](https://mermaid.js.org/intro/) — Diagram-as-code DSL; diagrams generated as Mermaid code by the LLM.
- [Mermaid.js GitHub](https://github.com/mermaid-js/mermaid) — Source for the vendored `frontend/static/vendor/mermaid.min.js`, run inside an `st.iframe()` with a JS `try/catch` and a 5-second render timeout instead of the dropped `streamlit-mermaid` component.
- [svg-pan-zoom](https://github.com/bumbu/svg-pan-zoom) — Pan/zoom for the rendered diagram SVG; vendored as `frontend/static/vendor/svg-pan-zoom.min.js`.

## Data & Storage

- [Python sqlite3 stdlib](https://docs.python.org/3/library/sqlite3.html) — Standard library SQLite interface used in `backend/analytics/db.py`.
- [Python dataclasses](https://docs.python.org/3/library/dataclasses.html) — Used for all data models.

## Package Management

- [uv Documentation](https://docs.astral.sh/uv/) — Fast Python package and project manager; replaces pip + venv.

## Testing

- [pytest Documentation](https://docs.pytest.org/) — Test framework used throughout `tests/`.

## LLM Provider Validation

**Automated (mocked) coverage** — `tests/test_content/test_llm_client.py`:

- **AnthropicAdapter** — plain-text `generate()`, tool-schema `generate()` returns dict, `make_cached_document_blocks()` cache control.
- **PortkeyAdapter** — same three cases as Anthropic, against a mocked `anthropic.Anthropic` client (Portkey reuses the Anthropic Messages API shape via its gateway).
- **OllamaAdapter** — `generate()` against a mocked OpenAI `chat.completions.create`:
  - `tool_calls` present → parsed function arguments returned as a dict, including `_fix_stringified_values` unwrapping nested JSON-as-string fields.
  - no `tool_calls`, content contains JSON → `_extract_json` handles plain JSON, a ```` ```json ```` fenced block, and a JSON object embedded in prose; `{"parameters": {...}}` wrapper is unwrapped.
  - plain-text response (no `tool_schema`) → returned as a string.
- `OllamaAdapter._translate_tool_schema` — Anthropic tool schema → OpenAI function-calling format.

These mocked tests do **not** exercise real network calls — they verify the adapters' request/response handling logic only.

**Manual checklist for live validation** (run once Ollama is installed locally and/or a real `PORTKEY_API_KEY` is configured):

1. **Ollama**
   - Install Ollama and run `ollama pull llama3.2` (or another tool-calling-capable model).
   - Set `AI_TUTOR_LLM_PROVIDER=ollama` in `.env`, start `ollama serve`.
   - `PYTHONPATH=. uv run streamlit run app.py`, upload a PDF, confirm module generation completes and a tutor session runs end-to-end.
   - Record pass/fail and any provider-specific quirks (e.g. malformed tool-call JSON from smaller models).
2. **Portkey**
   - Set `PORTKEY_API_KEY` to a real key and `AI_TUTOR_LLM_PROVIDER=portkey` in `.env`.
   - Repeat the same upload → module generation → tutor session flow.
   - Record pass/fail and any provider-specific quirks.

Results of this manual checklist are tracked as part of Phase 3 / Phase 31 follow-on validation (see `SPEC.md` §0 Phase 3 "Portkey / Ollama validation").
