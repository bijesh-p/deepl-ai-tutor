"""MCP server for assessment validation.

Exposes tools for evaluating question taxonomy and validating schemas.
Run standalone: PYTHONPATH=. uv run python -m mcp_servers.assessment_server.server
"""
from __future__ import annotations

import json
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("assessment_server")

BLOOMS_LEVELS = [
    "remember",
    "understand",
    "apply",
    "analyze",
    "evaluate",
    "create",
]

DIFFICULTY_MAP = {
    "remember": "easy",
    "understand": "easy",
    "apply": "medium",
    "analyze": "medium",
    "evaluate": "hard",
    "create": "hard",
}


@mcp.tool()
def evaluate_taxonomy(questions_json: str) -> str:
    """Evaluate and tag questions with Bloom's taxonomy level and difficulty.

    Input: JSON array of questions, each with 'question_text' and optional 'bloom_level'.
    Output: JSON array with added 'bloom_level' and 'difficulty' fields.
    """
    questions = json.loads(questions_json)

    for q in questions:
        bloom = q.get("bloom_level", "understand").lower()
        if bloom not in BLOOMS_LEVELS:
            bloom = "understand"
        q["bloom_level"] = bloom
        q["difficulty"] = DIFFICULTY_MAP[bloom]

    return json.dumps(questions)


@mcp.tool()
def validate_json_schema(data_json: str, schema_name: str) -> str:
    """Validate data against a known schema.

    Returns JSON with 'valid' boolean and 'errors' list.
    """
    data = json.loads(data_json)

    schemas = {
        "learning_module": {"required_keys": ["module_id", "title", "topics"]},
        "question": {"required_keys": ["question_id", "question_text", "options", "correct_answers"]},
        "question_bank": {"required_keys": ["module_id", "questions"]},
    }

    schema = schemas.get(schema_name)
    if not schema:
        return json.dumps({
            "valid": False,
            "errors": [f"Unknown schema: {schema_name}"],
        })

    errors = []
    for key in schema["required_keys"]:
        if key not in data:
            errors.append(f"Missing required key: {key}")

    return json.dumps({"valid": len(errors) == 0, "errors": errors})


if __name__ == "__main__":
    mcp.run()
