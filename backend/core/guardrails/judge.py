from __future__ import annotations

import logging

from backend.core.llm_client.base import BaseLLMClient

logger = logging.getLogger(__name__)

_MODERATION_SYSTEM = """You are a content-safety classifier for an educational AI tutoring application.
Students and instructors discuss a wide range of academic and technical subjects,
including ones that can sound alarming out of context: military history, war
crimes, biological pathogens, chemical reactions, weapons engineering,
cybersecurity exploits, criminal law, drug pharmacology, controversial
historical atrocities, human anatomy, and mental health topics. Discussing,
explaining, or analyzing these subjects in a normal academic, historical,
scientific, or pedagogical manner is EXPECTED and MUST NOT be flagged.

Flag content ONLY if it does one of the following:
- Gives actionable step-by-step operational instructions for causing real-world
  harm (e.g. synthesizing a weapon, building an explosive, executing a cyberattack
  against a real system) rather than explaining the underlying concept academically.
- Contains hate speech, slurs, or content that demeans a person/group based on a
  protected characteristic.
- Contains sexual content involving minors, or non-educational sexual content.
- Contains content that encourages self-harm, suicide, or harm to others as a
  call to action (not as a discussion of e.g. historical events or psychology).
- Contains personal attacks, harassment, or doxxing-style content directed at a
  real, identifiable individual.

When in doubt, classify as SAFE. Err strongly toward allowing normal academic
and technical content. Only flag clear, unambiguous violations."""

_MODERATION_SCHEMA = {
    "name": "classify_content_safety",
    "description": "Classify whether tutoring content violates safety policy.",
    "input_schema": {
        "type": "object",
        "properties": {
            "is_safe": {"type": "boolean", "description": "True if content is safe to show the student."},
            "category": {
                "type": "string",
                "enum": ["safe", "hate_speech", "sexual_content", "self_harm", "harassment", "dangerous_instructions", "other"],
            },
            "reason": {"type": "string", "description": "One sentence explaining the classification."},
        },
        "required": ["is_safe", "category", "reason"],
    },
}

_TOPIC_RELEVANCE_SYSTEM = """You are a scope-relevance classifier for an AI tutoring session. The student is
currently learning a specific topic. Your job is to decide whether the student's
message is a reasonable, on-topic question, answer, or request related to that
topic, the broader subject area, or normal study-session conversation (e.g.
"I don't understand", "can you explain again", "give me an example", clarifying
questions, tangential-but-related questions, or attempts to answer a question).

Be VERY permissive: allow related concepts, prerequisite questions, "why does
this matter" questions, requests for analogies, and questions that connect the
topic to other fields. Only flag a message as off-topic if it is CLEARLY and
ENTIRELY unrelated to the lesson — e.g. asking for help with unrelated homework
in a different subject, general chit-chat with no connection to learning,
requests to do something unrelated to tutoring (e.g. "write me a poem about
cats", "what's the weather"), or attempts to get the tutor to discuss something
completely unrelated to the course material.

When in doubt, classify as on-topic. A short or vague student answer is still
on-topic — only the clearly unrelated cases should be flagged."""

_TOPIC_RELEVANCE_SCHEMA = {
    "name": "classify_topic_relevance",
    "description": "Classify whether a student message is relevant to the current lesson topic.",
    "input_schema": {
        "type": "object",
        "properties": {
            "is_on_topic": {"type": "boolean"},
            "reason": {"type": "string", "description": "One sentence explaining the classification."},
        },
        "required": ["is_on_topic", "reason"],
    },
}


def check_content_moderation(inner: BaseLLMClient, text: str) -> str | None:
    """LLM-judge moderation check. Runs on output text/serialized-dict.
    Fails open (returns None) on any judge-call error or malformed
    response — a flaky classifier call must never block legitimate content."""
    if not text or not text.strip():
        return None
    try:
        result = inner.generate(
            f"Classify the following AI-generated tutoring content.\n\n---\n{text}\n---",
            system=_MODERATION_SYSTEM,
            tool_schema=_MODERATION_SCHEMA,
        )
        if not isinstance(result, dict):
            return None
        if result.get("is_safe", True):
            return None
        return f"{result.get('category', 'other')}: {result.get('reason', '')}"
    except Exception:
        logger.warning("Content-moderation judge call failed; failing open.", exc_info=True)
        return None


def check_topic_relevance(inner: BaseLLMClient, prompt_text: str, topic_context: str) -> str | None:
    """LLM-judge topic-relevance check. Runs on the full constructed prompt
    (which embeds the student's raw input) before the real generation call.
    Fails open on judge-call error."""
    if not prompt_text or not prompt_text.strip():
        return None
    try:
        result = inner.generate(
            f"Lesson topic: {topic_context}\n\nStudent's message:\n{prompt_text}\n\n"
            "Is this message on-topic for the lesson?",
            system=_TOPIC_RELEVANCE_SYSTEM,
            tool_schema=_TOPIC_RELEVANCE_SCHEMA,
        )
        if not isinstance(result, dict):
            return None
        if result.get("is_on_topic", True):
            return None
        return result.get("reason", "off_topic")
    except Exception:
        logger.warning("Topic-relevance judge call failed; failing open.", exc_info=True)
        return None
