from __future__ import annotations
import dataclasses
import json
import uuid
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
    source_location: str


@dataclass
class Section:
    section_id: str
    title: str
    body: str
    level: int
    images: list[ExtractedImage] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class Document:
    doc_id: str
    title: str
    source_filename: str
    source_type: SourceType
    sections: list[Section]
    total_pages: int

    def to_json(self) -> str:
        d = dataclasses.asdict(self)
        d["source_type"] = self.source_type.value
        return json.dumps(d)

    @classmethod
    def from_json(cls, data: str) -> Document:
        d = json.loads(data)
        source_type = SourceType(d.pop("source_type"))
        sections = [
            Section(
                section_id=s["section_id"],
                title=s["title"],
                body=s["body"],
                level=s["level"],
                images=[ExtractedImage(**img) for img in s.get("images", [])],
                metadata=s.get("metadata", {}),
            )
            for s in d.pop("sections")
        ]
        return cls(**d, source_type=source_type, sections=sections)
