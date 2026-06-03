from __future__ import annotations

import json
import dataclasses
from dataclasses import dataclass, field
from enum import Enum


class SourceType(Enum):
    PDF = "pdf"
    PPTX = "pptx"
    DOCX = "docx"


@dataclass
class ExtractedImage:
    image_id: str
    file_path: str
    caption: str | None
    source_location: str  # e.g. "page 3" or "slide 5"


@dataclass
class Section:
    section_id: str
    title: str
    body: str
    level: int  # heading depth: 1 = top-level
    images: list[ExtractedImage] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)  # speaker notes, table data, etc.


@dataclass
class Document:
    doc_id: str
    title: str
    source_filename: str
    source_type: SourceType
    sections: list[Section]
    total_pages: int

    def to_json(self) -> str:
        def _serialise(obj):
            if isinstance(obj, Enum):
                return obj.value
            if dataclasses.is_dataclass(obj):
                return dataclasses.asdict(obj)
            raise TypeError(f"Not serialisable: {type(obj)}")

        return json.dumps(dataclasses.asdict(self), default=_serialise, indent=2)

    @classmethod
    def from_json(cls, data: str | dict) -> Document:
        d = json.loads(data) if isinstance(data, str) else data
        sections = [
            Section(
                section_id=s["section_id"],
                title=s["title"],
                body=s["body"],
                level=s["level"],
                images=[ExtractedImage(**img) for img in s.get("images", [])],
                metadata=s.get("metadata", {}),
            )
            for s in d["sections"]
        ]
        return cls(
            doc_id=d["doc_id"],
            title=d["title"],
            source_filename=d["source_filename"],
            source_type=SourceType(d["source_type"]),
            sections=sections,
            total_pages=d["total_pages"],
        )
