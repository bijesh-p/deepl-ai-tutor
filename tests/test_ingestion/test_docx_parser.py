from __future__ import annotations

import os
import tempfile

import docx
from docx.oxml.ns import qn

from backend.ingestion.models import SourceType
from backend.ingestion.docx_parser import parse_docx


def _make_docx(content: list[tuple[str, str]], title: str = "") -> str:
    """Create a minimal .docx in a temp file and return its path.

    *content* is a list of (style_name, text) tuples.
    style_name: "Normal", "Heading 1", "Heading 2", etc.
    """
    d = docx.Document()
    if title:
        d.core_properties.title = title

    for style_name, text in content:
        d.add_paragraph(text, style=style_name)

    fd, path = tempfile.mkstemp(suffix=".docx")
    os.close(fd)
    d.save(path)
    return path


def _cleanup(path: str) -> None:
    if os.path.exists(path):
        os.unlink(path)


class TestDocxParser:
    def test_heading_based_sections(self):
        path = _make_docx(
            [
                ("Heading 1", "Introduction"),
                ("Normal", "This is the intro body."),
                ("Heading 1", "Chapter 1"),
                ("Normal", "Chapter one content."),
            ],
            title="Test Doc",
        )
        try:
            doc = parse_docx(path)
            assert doc.title == "Test Doc"
            assert doc.source_type == SourceType.DOCX
            assert len(doc.sections) == 2
            assert doc.sections[0].title == "Introduction"
            assert "intro body" in doc.sections[0].body
            assert doc.sections[1].title == "Chapter 1"
        finally:
            _cleanup(path)

    def test_heading_levels(self):
        path = _make_docx(
            [
                ("Heading 1", "Top Level"),
                ("Normal", "Top body."),
                ("Heading 2", "Sub Section"),
                ("Normal", "Sub body."),
            ]
        )
        try:
            doc = parse_docx(path)
            assert doc.sections[0].level == 1
            assert doc.sections[1].level == 2
        finally:
            _cleanup(path)

    def test_no_headings_falls_back_to_single_section(self):
        path = _make_docx(
            [
                ("Normal", "First paragraph."),
                ("Normal", "Second paragraph."),
            ],
            title="Flat Doc",
        )
        try:
            doc = parse_docx(path)
            assert len(doc.sections) == 1
            assert "First paragraph" in doc.sections[0].body
            assert "Second paragraph" in doc.sections[0].body
        finally:
            _cleanup(path)

    def test_title_falls_back_to_filename_stem(self):
        path = _make_docx([("Heading 1", "H"), ("Normal", "B.")])
        try:
            doc = parse_docx(path)
            assert doc.title  # not empty
            assert doc.source_filename.endswith(".docx")
        finally:
            _cleanup(path)

    def test_max_sections_cap(self):
        content = []
        for i in range(1, 6):
            content.append(("Heading 1", f"Section {i}"))
            content.append(("Normal", f"Body {i}."))
        path = _make_docx(content)
        try:
            doc = parse_docx(path, max_sections=3)
            assert len(doc.sections) <= 3
        finally:
            _cleanup(path)

    def test_sections_without_body_are_excluded(self):
        # A heading immediately followed by another heading → first section has no body
        path = _make_docx(
            [
                ("Heading 1", "Empty Section"),
                ("Heading 1", "Full Section"),
                ("Normal", "Has content."),
            ]
        )
        try:
            doc = parse_docx(path)
            # "Empty Section" has no body paragraphs → excluded
            assert len(doc.sections) == 1
            assert doc.sections[0].title == "Full Section"
        finally:
            _cleanup(path)

    def test_source_type_and_filename(self):
        path = _make_docx([("Heading 1", "H"), ("Normal", "B.")])
        try:
            doc = parse_docx(path)
            assert doc.source_type == SourceType.DOCX
            assert doc.source_filename.endswith(".docx")
        finally:
            _cleanup(path)

    def test_document_roundtrip_json(self):
        from backend.ingestion.models import Document
        path = _make_docx(
            [("Heading 1", "JSON Section"), ("Normal", "Roundtrip body.")],
            title="RT Doc",
        )
        try:
            doc = parse_docx(path)
            recovered = Document.from_json(doc.to_json())
            assert recovered.title == doc.title
            assert recovered.source_type == SourceType.DOCX
            assert len(recovered.sections) == len(doc.sections)
        finally:
            _cleanup(path)
