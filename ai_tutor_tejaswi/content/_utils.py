from __future__ import annotations
import json
import re


def parse_json_response(response: str | dict | list) -> dict | list:
    """Strip markdown fences and parse JSON from an LLM response."""
    if isinstance(response, (dict, list)):
        return response
    text = str(response).strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text.strip())
