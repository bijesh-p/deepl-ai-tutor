from __future__ import annotations
import os
import uuid

from ingestion.models import ExtractedImage


def save_image(
    image_bytes: bytes,
    output_dir: str,
    caption: str | None,
    source_location: str,
) -> ExtractedImage:
    os.makedirs(output_dir, exist_ok=True)
    image_id = str(uuid.uuid4())
    file_path = os.path.join(output_dir, f"{image_id}.png")
    with open(file_path, "wb") as f:
        f.write(image_bytes)
    return ExtractedImage(
        image_id=image_id,
        file_path=file_path,
        caption=caption,
        source_location=source_location,
    )


def extract_images(
    image_items: list[tuple[bytes, str | None, str]],
    output_dir: str,
) -> list[ExtractedImage]:
    """image_items: list of (image_bytes, caption, source_location)."""
    return [save_image(data, output_dir, caption, loc) for data, caption, loc in image_items]
