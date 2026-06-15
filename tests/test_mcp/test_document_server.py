"""Tests for document_server.extract_text_from_pdf via MCPClient.

Verifies the MCP tool's output is a drop-in replacement for calling
backend.ingestion.pdf_parser.parse_pdf() directly — i.e. Document.from_json()
parses it with the same title/sections/source_type.
"""
from __future__ import annotations

from pathlib import Path

from backend.core.mcp_client import get_client
from backend.ingestion.models import Document, SourceType

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample.pdf"


def test_extract_text_from_pdf_matches_parse_pdf():
    from backend.ingestion.pdf_parser import parse_pdf

    direct = parse_pdf(str(FIXTURE))

    doc_json = get_client("document_server").call(
        "extract_text_from_pdf", file_path=str(FIXTURE), max_pages=4
    )
    via_mcp = Document.from_json(doc_json)

    assert via_mcp.title == direct.title
    assert via_mcp.source_type == SourceType.PDF
    assert via_mcp.total_pages == direct.total_pages
    assert [s.title for s in via_mcp.sections] == [s.title for s in direct.sections]
    assert [s.body for s in via_mcp.sections] == [s.body for s in direct.sections]
