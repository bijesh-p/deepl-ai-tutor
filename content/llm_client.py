from __future__ import annotations

import json
import os
from enum import Enum


class Provider(Enum):
    ANTHROPIC = "anthropic"
    PORTKEY = "portkey"


class LLMClient:
    """Provider-agnostic LLM client supporting Claude via Anthropic or Portkey.

    All content and quiz modules call this class exclusively — no provider SDK
    is imported anywhere else in the codebase.

    Configuration via environment variables (see .env.example):
        AI_TUTOR_LLM_PROVIDER   — "anthropic" or "portkey"
        AI_TUTOR_LLM_API_KEY    — Anthropic API key (anthropic mode)
        AI_TUTOR_LLM_MODEL      — Claude model name
        AI_TUTOR_PORTKEY_API_KEY       — Portkey API key (portkey mode)
        AI_TUTOR_PORTKEY_VIRTUAL_KEY   — Portkey virtual key (portkey mode)
    """

    def __init__(
        self,
        provider: Provider,
        api_key: str,
        model: str,
        portkey_virtual_key: str | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self._client = self._build_client(provider, api_key, portkey_virtual_key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        response_schema: dict | None = None,
    ) -> str | dict:
        """Send a prompt and return the response.

        If response_schema is provided the response is parsed as JSON and
        returned as a dict; otherwise the raw text string is returned.
        The system prompt instructs the model to return valid JSON when a
        schema is supplied.
        """
        system_prompt = self._build_system(system, response_schema)
        messages = [{"role": "user", "content": prompt}]

        response = self._client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=messages,
        )
        text = response.content[0].text.strip()

        if response_schema is not None:
            return self._parse_json(text)
        return text

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> LLMClient:
        """Instantiate using environment variables."""
        provider_str = os.environ.get("AI_TUTOR_LLM_PROVIDER", "anthropic").lower()
        model = os.environ.get("AI_TUTOR_LLM_MODEL", "claude-opus-4-8")

        if provider_str == "portkey":
            return cls(
                provider=Provider.PORTKEY,
                api_key=os.environ["AI_TUTOR_PORTKEY_API_KEY"],
                model=model,
                portkey_virtual_key=os.environ["AI_TUTOR_PORTKEY_VIRTUAL_KEY"],
            )
        return cls(
            provider=Provider.ANTHROPIC,
            api_key=os.environ["AI_TUTOR_LLM_API_KEY"],
            model=model,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_client(
        self,
        provider: Provider,
        api_key: str,
        portkey_virtual_key: str | None,
    ):
        if provider == Provider.ANTHROPIC:
            import anthropic
            return anthropic.Anthropic(api_key=api_key)

        if provider == Provider.PORTKEY:
            import portkey_ai
            if not portkey_virtual_key:
                raise ValueError("portkey_virtual_key is required for Portkey provider")
            return portkey_ai.Portkey(
                api_key=api_key,
                virtual_key=portkey_virtual_key,
            )

        raise ValueError(f"Unknown provider: {provider}")

    @staticmethod
    def _build_system(system: str | None, schema: dict | None) -> str:
        parts = []
        if system:
            parts.append(system)
        if schema is not None:
            parts.append(
                "You must respond with valid JSON only — no markdown fences, "
                "no explanation text, just the raw JSON object or array. "
                f"The response must conform to this schema:\n{json.dumps(schema, indent=2)}"
            )
        return "\n\n".join(parts) if parts else "You are a helpful assistant."

    @staticmethod
    def _parse_json(text: str) -> dict | list:
        # Strip markdown fences if the model added them despite instructions
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        return json.loads(cleaned)
