from __future__ import annotations

import os
import tempfile

from backend.ingestion.models import Document, SourceType
from backend.ingestion.vtt_parser import parse_vtt

_FIXTURE = os.path.join(os.path.dirname(__file__), "..", "fixtures", "sample.vtt")

_SPEAKERS = {"Dr. Johnson", "Alice Chen", "Bob Kumar"}


def _make_vtt(content: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".vtt")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def _cleanup(path: str) -> None:
    if os.path.exists(path):
        os.unlink(path)


class TestVttParserFixture:
    def test_speaker_turns_produce_sections(self):
        doc = parse_vtt(_FIXTURE)
        assert len(doc.sections) >= 2
        for s in doc.sections:
            for name in _SPEAKERS:
                assert name not in s.title, f"Speaker name '{name}' leaked into title: {s.title}"

    def test_no_speaker_names_in_output(self):
        doc = parse_vtt(_FIXTURE)
        for s in doc.sections:
            for name in _SPEAKERS:
                assert name not in s.title, f"Name in title: {s.title}"
                assert name not in s.body, f"Name '{name}' in body of section '{s.title}'"

    def test_qa_extraction(self):
        doc = parse_vtt(_FIXTURE)
        all_text = " ".join(s.body for s in doc.sections)
        assert "**Q:**" in all_text, "Q&A questions should be tagged with **Q:**"
        assert "**A:**" in all_text, "Q&A answers should be tagged with **A:**"

    def test_chatter_stripped(self):
        doc = parse_vtt(_FIXTURE)
        all_text = " ".join(s.body for s in doc.sections)
        assert "can you hear me" not in all_text.lower()
        assert "is my screen visible" not in all_text.lower()
        assert "have a great day" not in all_text.lower()

    def test_source_type_is_vtt(self):
        doc = parse_vtt(_FIXTURE)
        assert doc.source_type == SourceType.VTT

    def test_document_roundtrip_json(self):
        doc = parse_vtt(_FIXTURE)
        recovered = Document.from_json(doc.to_json())
        assert recovered.title == doc.title
        assert recovered.source_type == SourceType.VTT
        assert len(recovered.sections) == len(doc.sections)
        for orig, rec in zip(doc.sections, recovered.sections):
            assert orig.title == rec.title
            assert orig.body == rec.body


class TestVttParserEdgeCases:
    def test_time_gap_segmentation(self):
        vtt = (
            "WEBVTT\n\n"
            "00:00:01.000 --> 00:00:10.000\n"
            "Machine learning is a subset of artificial intelligence that focuses on learning from data.\n\n"
            "00:01:00.000 --> 00:01:10.000\n"
            "Deep learning uses multiple layers of neural networks to learn representations.\n"
        )
        path = _make_vtt(vtt)
        try:
            doc = parse_vtt(path)
            assert len(doc.sections) >= 2, f"Expected >=2 sections from time gap, got {len(doc.sections)}"
        finally:
            _cleanup(path)

    def test_fixed_chunk_fallback(self):
        words = " ".join(f"word{i}" for i in range(1200))
        vtt = f"WEBVTT\n\n00:00:01.000 --> 00:10:00.000\n{words}\n"
        path = _make_vtt(vtt)
        try:
            doc = parse_vtt(path)
            assert len(doc.sections) >= 2, "Long transcript should be chunked into multiple sections"
            for s in doc.sections:
                assert s.title.startswith("Part ")
        finally:
            _cleanup(path)

    def test_single_cue(self):
        vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:10.000\nNeural networks process data in layers.\n"
        path = _make_vtt(vtt)
        try:
            doc = parse_vtt(path)
            assert len(doc.sections) == 1
            assert "Neural networks" in doc.sections[0].body
        finally:
            _cleanup(path)

    def test_empty_file(self):
        vtt = "WEBVTT\n\n"
        path = _make_vtt(vtt)
        try:
            doc = parse_vtt(path)
            assert len(doc.sections) == 0
        finally:
            _cleanup(path)

    def test_max_sections_cap(self):
        cues = []
        for i in range(20):
            start = i * 60
            end = start + 10
            h, m, s = start // 3600, (start % 3600) // 60, start % 60
            eh, em, es = end // 3600, (end % 3600) // 60, end % 60
            cues.append(
                f"{h:02d}:{m:02d}:{s:02d}.000 --> {eh:02d}:{em:02d}:{es:02d}.000\n"
                f"Section {i+1} content about topic number {i+1} with enough words to fill it out."
            )
        vtt = "WEBVTT\n\n" + "\n\n".join(cues)
        path = _make_vtt(vtt)
        try:
            doc = parse_vtt(path, max_sections=5)
            assert len(doc.sections) <= 5
        finally:
            _cleanup(path)

    def test_speaker_prefix_format(self):
        vtt = (
            "WEBVTT\n\n"
            "00:00:01.000 --> 00:00:10.000\n"
            "Speaker 1: Gradient descent is an optimization algorithm used to minimize the loss function.\n\n"
            "00:00:11.000 --> 00:00:18.000\n"
            "Speaker 2: What happens when the learning rate is too large?\n\n"
            "00:00:19.000 --> 00:00:30.000\n"
            "Speaker 1: The model will overshoot the minimum and may diverge instead of converging.\n"
        )
        path = _make_vtt(vtt)
        try:
            doc = parse_vtt(path)
            for s in doc.sections:
                assert "Speaker 1" not in s.body
                assert "Speaker 2" not in s.body
                assert "Speaker 1" not in s.title
                assert "Speaker 2" not in s.title
        finally:
            _cleanup(path)

    def test_html_tags_stripped(self):
        vtt = (
            "WEBVTT\n\n"
            "00:00:01.000 --> 00:00:10.000\n"
            "<b>Important:</b> The <i>activation function</i> determines the output of a neuron.\n"
        )
        path = _make_vtt(vtt)
        try:
            doc = parse_vtt(path)
            body = doc.sections[0].body
            assert "<b>" not in body
            assert "<i>" not in body
            assert "activation function" in body
        finally:
            _cleanup(path)

    def test_invalid_file_raises(self):
        path = _make_vtt("This is not a VTT file\nJust plain text.")
        try:
            import pytest
            with pytest.raises(ValueError, match="Not a valid WebVTT"):
                parse_vtt(path)
        finally:
            _cleanup(path)

    def test_bom_handling(self):
        vtt = "﻿WEBVTT\n\n00:00:01.000 --> 00:00:10.000\nBOM test content about machine learning.\n"
        path = _make_vtt(vtt)
        try:
            doc = parse_vtt(path)
            assert len(doc.sections) == 1
            assert "BOM test content" in doc.sections[0].body
        finally:
            _cleanup(path)
