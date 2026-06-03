from __future__ import annotations

import uuid
from pathlib import Path

import fitz  # PyMuPDF

from ingestion.models import ExtractedImage


def extract_images(
    page: fitz.Page,
    doc_id: str,
    page_num: int,
    upload_dir: str = "data/uploads",
) -> list[ExtractedImage]:
    """Extract all raster images from a PyMuPDF page and save them as PNGs.

    Returns one ExtractedImage per image found. Images smaller than 50×50 px
    are skipped (typically decorative bullets or borders).
    """
    images: list[ExtractedImage] = []
    out_dir = Path(upload_dir) / doc_id / "images"
    out_dir.mkdir(parents=True, exist_ok=True)

    for img_info in page.get_images(full=True):
        xref = img_info[0]
        base_image = page.parent.extract_image(xref)
        width = base_image.get("width", 0)
        height = base_image.get("height", 0)

        if width < 50 or height < 50:
            continue

        image_id = str(uuid.uuid4())
        filename = f"{image_id}.png"
        file_path = out_dir / filename

        # Convert to PNG via a pixmap so format is always consistent
        pix = fitz.Pixmap(base_image["image"])
        if pix.n > 4:  # CMYK or similar — convert to RGB first
            pix = fitz.Pixmap(fitz.csRGB, pix)
        pix.save(str(file_path))

        images.append(
            ExtractedImage(
                image_id=image_id,
                file_path=str(file_path),
                caption=None,
                source_location=f"page {page_num}",
            )
        )

    return images
