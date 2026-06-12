from pathlib import Path
import pytest
from backend.ingestion.pdf_parser import parse_pdf
from backend.ingestion.models import SourceType

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample.pdf"


def test_parse_returns_document():
    doc = parse_pdf(str(FIXTURE))
    assert doc.doc_id
    assert doc.title == "Sample ML Document"
    assert doc.source_type == SourceType.PDF
    assert doc.total_pages == 3


def test_sections_from_toc():
    doc = parse_pdf(str(FIXTURE))
    assert len(doc.sections) == 3
    titles = [s.title for s in doc.sections]
    assert "Introduction to Machine Learning" in titles
    assert "Supervised Learning" in titles
    assert "Unsupervised Learning" in titles


def test_section_body_non_empty():
    doc = parse_pdf(str(FIXTURE))
    for section in doc.sections:
        assert section.body.strip(), f"Section '{section.title}' has empty body"


def test_roundtrip_json():
    from backend.ingestion.models import Document
    doc = parse_pdf(str(FIXTURE))
    restored = Document.from_json(doc.to_json())
    assert restored.doc_id == doc.doc_id
    assert restored.title == doc.title
    assert len(restored.sections) == len(doc.sections)
