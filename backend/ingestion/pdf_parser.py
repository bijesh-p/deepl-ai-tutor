from __future__ import annotations

import uuid
from pathlib import Path

import fitz  # PyMuPDF

from backend.ingestion.models import Document, Section, SourceType

_DEFAULT_MAX_PAGES = 4


def parse_pdf(file_path: str, max_pages: int = _DEFAULT_MAX_PAGES) -> Document:
    """Parse a PDF into the unified Document model.

    Only the first *max_pages* pages are read; the rest are ignored so that
    LLM context stays bounded regardless of PDF length.

    Sections are derived from the PDF outline (bookmarks) when available;
    otherwise each page becomes its own section.
    """
    path = Path(file_path)
    doc_id = str(uuid.uuid4())

    pdf = fitz.open(str(path))
    total_pages = pdf.page_count
    effective_pages = min(total_pages, max_pages)

    toc = pdf.get_toc()  # [[level, title, page], ...]
    sections = (
        _sections_from_toc(pdf, toc, effective_pages)
        if toc
        else _sections_from_pages(pdf, effective_pages)
    )

    title = _extract_title(pdf, path)
    pdf.close()

    return Document(
        doc_id=doc_id,
        title=title,
        source_filename=path.name,
        source_type=SourceType.PDF,
        sections=sections,
        total_pages=effective_pages,
    )


def _extract_title(pdf: fitz.Document, path: Path) -> str:
    meta = pdf.metadata or {}
    return meta.get("title") or path.stem


def _sections_from_toc(
    pdf: fitz.Document, toc: list, effective_pages: int
) -> list[Section]:
    # Keep only TOC entries whose section starts within the page limit
    visible_toc = [entry for entry in toc if entry[2] <= effective_pages]

    sections: list[Section] = []
    for i, (level, title, start_page) in enumerate(visible_toc):
        next_start = visible_toc[i + 1][2] if i + 1 < len(visible_toc) else effective_pages + 1
        end_page = min(next_start - 1, effective_pages)
        body = _extract_text_range(pdf, start_page - 1, end_page - 1)
        sections.append(
            Section(
                section_id=str(uuid.uuid4()),
                title=title.strip() or f"Section {i + 1}",
                body=body,
                level=level,
            )
        )

    return sections


def _sections_from_pages(pdf: fitz.Document, effective_pages: int) -> list[Section]:
    sections: list[Section] = []

    for page_num in range(effective_pages):
        page = pdf[page_num]
        body = page.get_text("text").strip()
        if not body:
            continue
        sections.append(
            Section(
                section_id=str(uuid.uuid4()),
                title=f"Page {page_num + 1}",
                body=body,
                level=1,
            )
        )

    return sections


def _extract_text_range(pdf: fitz.Document, start: int, end: int) -> str:
    parts: list[str] = []
    for page_num in range(start, min(end + 1, pdf.page_count)):
        text = pdf[page_num].get_text("text").strip()
        if text:
            parts.append(text)
    return "\n\n".join(parts)
