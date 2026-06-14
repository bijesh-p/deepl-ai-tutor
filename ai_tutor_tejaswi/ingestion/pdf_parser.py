from __future__ import annotations
import os
import uuid

import fitz  # PyMuPDF

from ingestion.image_extractor import save_image
from ingestion.models import Document, Section, SourceType


def parse_pdf(file_path: str) -> Document:
    doc_id = str(uuid.uuid4())
    upload_dir = os.path.join(
        os.environ.get("AI_TUTOR_UPLOAD_DIR", "data/uploads"), doc_id, "images"
    )

    pdf = fitz.open(file_path)
    sections: list[Section] = []

    for page_num, page in enumerate(pdf):
        blocks = page.get_text("dict")["blocks"]
        images: list = []

        font_sizes = [
            span.get("size", 12)
            for block in blocks
            if block.get("type") == 0
            for line in block.get("lines", [])
            for span in line.get("spans", [])
        ]
        avg_size = sum(font_sizes) / len(font_sizes) if font_sizes else 12

        heading_parts: list[str] = []
        body_parts: list[str] = []

        for block in blocks:
            if block.get("type") != 0:
                continue
            texts: list[str] = []
            is_heading = False
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span.get("size", 12) > avg_size * 1.2:
                        is_heading = True
                    texts.append(span.get("text", ""))
            block_text = " ".join(texts).strip()
            if not block_text:
                continue
            if is_heading:
                heading_parts.append(block_text)
            else:
                body_parts.append(block_text)

        for img_info in page.get_images(full=True):
            xref = img_info[0]
            try:
                base_image = pdf.extract_image(xref)
                ext_img = save_image(
                    base_image["image"], upload_dir, None, f"page {page_num + 1}"
                )
                images.append(ext_img)
            except Exception:
                pass

        title = heading_parts[0] if heading_parts else f"Page {page_num + 1}"
        extra_headings = "\n".join(heading_parts[1:])
        body = "\n".join(filter(None, [extra_headings, "\n".join(body_parts)]))

        sections.append(
            Section(
                section_id=str(uuid.uuid4()),
                title=title,
                body=body,
                level=1,
                images=images,
            )
        )

    doc_title = (
        pdf.metadata.get("title")
        or os.path.splitext(os.path.basename(file_path))[0]
    )

    return Document(
        doc_id=doc_id,
        title=doc_title,
        source_filename=os.path.basename(file_path),
        source_type=SourceType.PDF,
        sections=sections,
        total_pages=len(pdf),
    )
