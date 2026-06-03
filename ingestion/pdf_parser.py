from __future__ import annotations

import os
import uuid
from pathlib import Path

import fitz  # PyMuPDF

from ingestion.image_extractor import extract_images
from ingestion.models import Document, Section, SourceType


# Ratio threshold: a span's font size must be this many times the median
# body font size to be treated as a heading.
_HEADING_RATIO = 1.15

# Minimum characters for a text block to count as body content.
_MIN_BODY_CHARS = 20


def _median_font_size(page: fitz.Page) -> float:
    sizes = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if span.get("text", "").strip():
                    sizes.append(span["size"])
    if not sizes:
        return 12.0
    sizes.sort()
    mid = len(sizes) // 2
    return sizes[mid]


def _is_heading(span_size: float, median: float) -> bool:
    return span_size >= median * _HEADING_RATIO


def parse_pdf(
    file_path: str,
    upload_dir: str = "data/uploads",
) -> Document:
    """Parse a PDF file into a Document with sections and extracted images.

    Heading detection uses a font-size heuristic: any span whose font size
    is at least 1.15× the median body font size on that page is treated as
    a section heading. Text following a heading is collected into its body
    until the next heading is encountered.
    """
    path = Path(file_path)
    doc_id = str(uuid.uuid4())
    pdf = fitz.open(str(path))

    sections: list[Section] = []
    current_title: str = path.stem.replace("_", " ").title()
    current_body_parts: list[str] = []
    current_images: list = []
    section_index = 0

    def _flush_section() -> None:
        nonlocal current_title, current_body_parts, current_images, section_index
        body = "\n".join(current_body_parts).strip()
        if body or current_images:
            sections.append(
                Section(
                    section_id=str(uuid.uuid4()),
                    title=current_title,
                    body=body,
                    level=1,
                    images=list(current_images),
                )
            )
            section_index += 1
        current_body_parts = []
        current_images = []

    for page_num, page in enumerate(pdf, start=1):
        median = _median_font_size(page)
        page_images = extract_images(page, doc_id, page_num, upload_dir)

        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 0:  # skip non-text blocks
                continue

            for line in block.get("lines", []):
                line_text = ""
                line_max_size = 0.0
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if text:
                        line_text += text + " "
                        line_max_size = max(line_max_size, span.get("size", 0))

                line_text = line_text.strip()
                if not line_text:
                    continue

                if _is_heading(line_max_size, median) and len(line_text) < 120:
                    _flush_section()
                    current_title = line_text
                else:
                    if len(line_text) >= _MIN_BODY_CHARS or current_body_parts:
                        current_body_parts.append(line_text)

        # Attach images to the current section being built
        current_images.extend(page_images)

    _flush_section()  # flush the last section

    # Derive document title: first section title or filename
    doc_title = sections[0].title if sections else path.stem.replace("_", " ").title()
    total_pages = pdf.page_count
    pdf.close()

    return Document(
        doc_id=doc_id,
        title=doc_title,
        source_filename=path.name,
        source_type=SourceType.PDF,
        sections=sections,
        total_pages=total_pages,
    )
