# references.md — Annotated Technology References

## Document Parsing

- [PyMuPDF Documentation](https://pymupdf.readthedocs.io/) — Python bindings for MuPDF; used for PDF text extraction and TOC parsing in `ingestion/pdf_parser.py`.
- [PyMuPDF GitHub](https://github.com/pymupdf/PyMuPDF) — Source and issue tracker.

## LLM Integration

- [Anthropic Python SDK](https://github.com/anthropic/anthropic-sdk-python) — Official SDK used in `content/llm_client.py`.
- [Anthropic API Docs — Tool Use](https://docs.anthropic.com/en/docs/tool-use) — Structured output via tool-use; used for all LLM calls to get typed JSON responses.
- [Anthropic API Docs — Prompt Caching](https://docs.anthropic.com/en/docs/prompt-caching) — Cache control on system prompt and document blocks to reduce token costs on repeated enrichment calls.
- [Claude Model Overview](https://docs.anthropic.com/en/docs/models-overview) — Model IDs and capabilities; Phase 1 uses `claude-sonnet-4-6`.

## Frontend

- [Streamlit Documentation](https://docs.streamlit.io/) — Python web framework powering all UI pages.
- [streamlit-mermaid](https://github.com/jhavens1566/streamlit-mermaid) — Streamlit component for rendering Mermaid diagrams client-side in `frontend/module_viewer.py`.
- [Mermaid Diagram Syntax](https://mermaid.js.org/intro/) — Diagram-as-code DSL; diagrams are generated as Mermaid code strings by the LLM.

## Data & Storage

- [Python sqlite3 stdlib](https://docs.python.org/3/library/sqlite3.html) — Standard library SQLite interface used in `analytics/db.py`.
- [Python dataclasses](https://docs.python.org/3/library/dataclasses.html) — Used for all data models across all five work streams.

## Package Management

- [uv Documentation](https://docs.astral.sh/uv/) — Fast Python package and project manager; replaces pip + venv.
- [uv GitHub](https://github.com/astral-sh/uv) — Source and issue tracker.

## Testing

- [pytest Documentation](https://docs.pytest.org/) — Test framework used throughout `tests/`.
