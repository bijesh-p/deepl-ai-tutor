from __future__ import annotations
import os
import uuid

from docx import Document as DocxDoc

from ingestion.image_extractor import save_image
from ingestion.models import Document, Section, SourceType


def parse_docx(file_path: str) -> Document:
    doc_id = str(uuid.uuid4())
    upload_dir = os.path.join(
        os.environ.get("AI_TUTOR_UPLOAD_DIR", "data/uploads"), doc_id, "images"
    )

    docx = DocxDoc(file_path)
    sections: list[Section] = []
    current: Section | None = None

    for para in docx.paragraphs:
        style = para.style.name
        if style.startswith("Heading"):
            if current is not None:
                sections.append(current)
            level = int(style[-1]) if style[-1].isdigit() else 1
            current = Section(
                section_id=str(uuid.uuid4()),
                title=para.text,
                body="",
                level=level,
            )
        else:
            if current is None:
                current = Section(
                    section_id=str(uuid.uuid4()),
                    title=os.path.splitext(os.path.basename(file_path))[0],
                    body="",
                    level=1,
                )
            if para.text.strip():
                current.body += para.text + "\n"

    if current is not None:
        sections.append(current)

    # Attach embedded images to the last section that existed at extraction time
    for i, rel in enumerate(docx.part.rels.values()):
        if "image" in rel.reltype:
            try:
                ext_img = save_image(
                    rel.target_part.blob,
                    upload_dir,
                    None,
                    f"embedded image {i + 1}",
                )
                if sections:
                    sections[-1].images.append(ext_img)
            except Exception:
                pass

    title = (
        docx.core_properties.title
        or os.path.splitext(os.path.basename(file_path))[0]
    )

    return Document(
        doc_id=doc_id,
        title=title,
        source_filename=os.path.basename(file_path),
        source_type=SourceType.DOCX,
        sections=sections,
        total_pages=len(sections),
    )
