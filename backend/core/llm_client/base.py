from __future__ import annotations

from abc import ABC, abstractmethod


class BaseLLMClient(ABC):
    """Abstract base for all LLM provider adapters.

    Callers always pass Anthropic-format tool schemas.
    Adapters translate internally if needed.
    """

    provider: str
    model: str

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system: str | None = None,
        tool_schema: dict | None = None,
        cached_blocks: list[dict] | None = None,
    ) -> str | dict:
        """Send a prompt and return plain text or parsed tool-use dict."""
        ...

    def make_cached_document_blocks(self, text: str) -> list[dict]:
        """Wrap document text for reuse across calls.

        Subclasses that support prompt caching should override this.
        The default returns a plain text block (no caching).
        """
        return [{"type": "text", "text": text}]
