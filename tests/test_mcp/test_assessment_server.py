"""Tests for assessment_server.validate_json_schema via MCPClient."""
from __future__ import annotations

import json

from backend.core.mcp_client import get_client


def _call(data: dict, schema_name: str) -> dict:
    return json.loads(
        get_client("assessment_server").call(
            "validate_json_schema",
            data_json=json.dumps(data),
            schema_name=schema_name,
        )
    )


def test_validate_learning_module_valid():
    result = _call({"module_id": "m1", "title": "Test", "topics": []}, "learning_module")
    assert result["valid"] is True
    assert result["errors"] == []


def test_validate_question_valid():
    data = {
        "question_id": "q1",
        "question_text": "What is X?",
        "options": ["A", "B", "C", "D"],
        "correct_answers": [0],
    }
    result = _call(data, "question")
    assert result["valid"] is True
    assert result["errors"] == []


def test_validate_question_bank_valid():
    result = _call({"module_id": "m1", "questions": []}, "question_bank")
    assert result["valid"] is True
    assert result["errors"] == []


def test_validate_learning_module_missing_key():
    result = _call({"module_id": "m1", "title": "T"}, "learning_module")  # missing topics
    assert result["valid"] is False
    assert any("topics" in e for e in result["errors"])


def test_validate_question_missing_keys():
    result = _call({"question_id": "q1"}, "question")  # missing question_text, options, correct_answers
    assert result["valid"] is False
    assert len(result["errors"]) >= 3


def test_validate_unknown_schema():
    result = _call({}, "nonexistent_schema")
    assert result["valid"] is False
    assert any("Unknown schema" in e for e in result["errors"])
