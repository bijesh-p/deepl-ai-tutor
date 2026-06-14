from ingestion.models import Document, ExtractedImage, Section, SourceType


def _sample_doc() -> Document:
    img = ExtractedImage(
        image_id="img-1", file_path="/tmp/img.png", caption="Figure 1", source_location="page 1"
    )
    section = Section(
        section_id="sec-1", title="Intro", body="Hello world", level=1, images=[img]
    )
    return Document(
        doc_id="doc-1",
        title="Test Doc",
        source_filename="test.pdf",
        source_type=SourceType.PDF,
        sections=[section],
        total_pages=1,
    )


def test_round_trip_json():
    doc = _sample_doc()
    restored = Document.from_json(doc.to_json())

    assert restored.doc_id == doc.doc_id
    assert restored.source_type == SourceType.PDF
    assert len(restored.sections) == 1
    sec = restored.sections[0]
    assert sec.title == "Intro"
    assert len(sec.images) == 1
    assert sec.images[0].caption == "Figure 1"


def test_source_type_serialises_as_string():
    import json
    d = json.loads(_sample_doc().to_json())
    assert d["source_type"] == "pdf"


def test_section_metadata_preserved():
    doc = _sample_doc()
    doc.sections[0].metadata = {"speaker_notes": "hello"}
    restored = Document.from_json(doc.to_json())
    assert restored.sections[0].metadata == {"speaker_notes": "hello"}
