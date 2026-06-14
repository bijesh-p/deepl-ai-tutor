# references.md — Annotated Technology References

## Document Parsing

- [PyMuPDF Documentation](https://pymupdf.readthedocs.io/) — Python bindings for MuPDF; used for PDF text extraction and TOC parsing in `backend/ingestion/pdf_parser.py`.
- [PyMuPDF GitHub](https://github.com/pymupdf/PyMuPDF) — Source and issue tracker.

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

## Model Context Protocol (MCP)

- [MCP Specification](https://modelcontextprotocol.io/) — Protocol for LLM tool access; three MCP servers in `mcp_servers/`.
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) — Python SDK for building MCP servers and clients.

## Vector Store & Embeddings

- [ChromaDB Documentation](https://docs.trychroma.com/) — Embedding database for semantic search over document chunks in `mcp_servers/storage_server/`.
- [ChromaDB GitHub](https://github.com/chroma-core/chroma) — Source and issue tracker.
- [Sentence Transformers](https://www.sbert.net/) — Framework for sentence embeddings; uses `all-MiniLM-L6-v2` model.
- [all-MiniLM-L6-v2 on HuggingFace](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) — Lightweight embedding model (384 dimensions, 22M params).

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
- [streamlit-mermaid](https://github.com/jhavens1566/streamlit-mermaid) — Streamlit component for rendering Mermaid diagrams.
- [Mermaid Diagram Syntax](https://mermaid.js.org/intro/) — Diagram-as-code DSL; diagrams generated as Mermaid code by the LLM.

## Data & Storage

- [Python sqlite3 stdlib](https://docs.python.org/3/library/sqlite3.html) — Standard library SQLite interface used in `backend/analytics/db.py`.
- [Python dataclasses](https://docs.python.org/3/library/dataclasses.html) — Used for all data models.

## Package Management

- [uv Documentation](https://docs.astral.sh/uv/) — Fast Python package and project manager; replaces pip + venv.

## Testing

- [pytest Documentation](https://docs.pytest.org/) — Test framework used throughout `tests/`.
