from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from ingestion.models import Document, SourceType
from ingestion.pdf_parser import parse_pdf

FIXTURES = Path(__file__).parent.parent / "fixtures"
SAMPLE_PDF = FIXTURES / "sample.pdf"


@pytest.fixture
def parsed_doc(tmp_path) -> Document:
    return parse_pdf(str(SAMPLE_PDF), upload_dir=str(tmp_path))


def test_returns_document_type(parsed_doc):
    assert isinstance(parsed_doc, Document)


def test_source_type_is_pdf(parsed_doc):
    assert parsed_doc.source_type == SourceType.PDF


def test_source_filename(parsed_doc):
    assert parsed_doc.source_filename == "sample.pdf"


def test_total_pages(parsed_doc):
    assert parsed_doc.total_pages == 4


def test_sections_extracted(parsed_doc):
    assert len(parsed_doc.sections) >= 2, (
        f"Expected at least 2 sections, got {len(parsed_doc.sections)}"
    )


def test_section_bodies_non_empty(parsed_doc):
    for sec in parsed_doc.sections:
        assert sec.body.strip(), f"Section '{sec.title}' has empty body"


def test_section_ids_unique(parsed_doc):
    ids = [s.section_id for s in parsed_doc.sections]
    assert len(ids) == len(set(ids)), "Section IDs are not unique"


def test_doc_id_is_set(parsed_doc):
    assert parsed_doc.doc_id and len(parsed_doc.doc_id) > 0


def test_round_trip_serialisation(parsed_doc):
    json_str = parsed_doc.to_json()
    restored = Document.from_json(json_str)
    assert restored.doc_id == parsed_doc.doc_id
    assert restored.total_pages == parsed_doc.total_pages
    assert len(restored.sections) == len(parsed_doc.sections)
    assert restored.source_type == SourceType.PDF


def test_known_heading_appears(parsed_doc):
    titles = [s.title for s in parsed_doc.sections]
    assert any("Machine Learning" in t or "Introduction" in t for t in titles), (
        f"Expected a heading containing 'Machine Learning', got: {titles}"
    )


def test_missing_file_raises():
    with pytest.raises(Exception):
        parse_pdf("nonexistent/path/file.pdf")
