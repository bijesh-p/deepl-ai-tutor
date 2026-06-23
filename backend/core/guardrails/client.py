from __future__ import annotations

import json

from backend.core.guardrails.config import (
    guardrails_enabled,
    moderation_enabled,
    topic_relevance_enabled,
)
from backend.core.guardrails import judge
from backend.core.guardrails.exceptions import GuardrailViolation
from backend.core.guardrails.rules import check_output_quality, check_prompt_injection
from backend.core.llm_client.base import BaseLLMClient


class GuardrailedLLMClient(BaseLLMClient):
    """Wraps any BaseLLMClient adapter with input/output guardrail checks.

    Input checks (run before the real call, so a blocked request never
    burns a generation): prompt-injection (always), topic-relevance (only
    when `topic_context` is passed — call sites opt in).
    Output checks (run after the real call): output-quality (always,
    string results only), content-moderation (always).

    Judge-based checks call `self._inner` directly, never `self` — calling
    through the wrapper again would recurse into these same checks.
    """

    def __init__(self, inner: BaseLLMClient):
        self._inner = inner
        self.provider = inner.provider
        self.model = inner.model

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        tool_schema: dict | None = None,
        cached_blocks: list[dict] | None = None,
        topic_context: str | None = None,
        skip_input_guardrails: bool = False,
    ) -> str | dict:
        if not guardrails_enabled():
            return self._inner.generate(prompt, system, tool_schema, cached_blocks)

        if not skip_input_guardrails:
            reason = check_prompt_injection(prompt)
            if reason:
                raise GuardrailViolation(
                    "prompt_injection",
                    "Your message couldn't be processed because it looked like an "
                    "attempt to manipulate the tutor's instructions. Please rephrase "
                    "your question normally.",
                    details=reason,
                )

            if topic_context and topic_relevance_enabled():
                reason = judge.check_topic_relevance(self._inner, prompt, topic_context)
                if reason:
                    raise GuardrailViolation(
                        "topic_relevance",
                        "That looks like it's not related to the current lesson topic. "
                        "Try asking something about the concept we're covering, or use "
                        "'Back to Library' to switch topics.",
                        details=reason,
                    )

        result = self._inner.generate(prompt, system, tool_schema, cached_blocks)

        reason = check_output_quality(result if isinstance(result, str) else None)
        if reason:
            raise GuardrailViolation(
                "output_quality",
                "The tutor's response couldn't be shown because it didn't look "
                "right. Please try again.",
                details=reason,
            )

        if moderation_enabled():
            text_for_review = result if isinstance(result, str) else json.dumps(result)
            reason = judge.check_content_moderation(self._inner, text_for_review)
            if reason:
                raise GuardrailViolation(
                    "content_moderation",
                    "The tutor's response couldn't be shown because it didn't pass "
                    "a safety check. Please try again — if this keeps happening, "
                    "try rephrasing your question.",
                    details=reason,
                )

        return result

    def make_cached_document_blocks(self, text: str) -> list[dict]:
        return self._inner.make_cached_document_blocks(text)
