from __future__ import annotations

import os

_FALSY = ("false", "0", "no")


def _flag(name: str, default: bool = True) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in _FALSY


def guardrails_enabled() -> bool:
    return _flag("AI_TUTOR_GUARDRAILS_ENABLED")


def moderation_enabled() -> bool:
    return _flag("AI_TUTOR_GUARDRAILS_MODERATION_ENABLED")


def topic_relevance_enabled() -> bool:
    return _flag("AI_TUTOR_GUARDRAILS_TOPIC_RELEVANCE_ENABLED")
