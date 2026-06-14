from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
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
    source_location: str  # e.g. "page 3"


@dataclass
class Section:
    section_id: str
    title: str
    body: str
    level: int  # 1 = top-level heading
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
        d = asdict(self)
        d["source_type"] = self.source_type.value
        return json.dumps(d)

    @classmethod
    def from_json(cls, data: str) -> Document:
        d = json.loads(data)
        d["source_type"] = SourceType(d["source_type"])
        d["sections"] = [
            Section(
                **{
                    **s,
                    "images": [ExtractedImage(**img) for img in s["images"]],
                }
            )
            for s in d["sections"]
        ]
        return cls(**d)
