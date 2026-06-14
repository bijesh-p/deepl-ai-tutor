from __future__ import annotations
import json
import os
import re
import time
import uuid

from content._utils import parse_json_response

_OLLAMA_BASE = "http://localhost:11434/v1"


def make_llm_client() -> "LLMClient":
    """Factory that returns the right client based on AI_TUTOR_LLM_PROVIDER."""
    provider = os.environ.get("AI_TUTOR_LLM_PROVIDER", "openai").lower()
    if provider == "demo":
        return DemoLLMClient()
    return LLMClient()


class LLMClient:
    def __init__(self) -> None:
        self.provider = os.environ.get("AI_TUTOR_LLM_PROVIDER", "openai").lower()
        self.api_key = os.environ.get("AI_TUTOR_LLM_API_KEY", "")
        self.model = os.environ.get("AI_TUTOR_LLM_MODEL", "gpt-4o")
        self.timeout = 60
        self._client = self._init_client()

    def _init_client(self):
        if self.provider == "openai":
            from openai import OpenAI
            return OpenAI(api_key=self.api_key, timeout=self.timeout)
        if self.provider == "anthropic":
            from anthropic import Anthropic
            return Anthropic(api_key=self.api_key, timeout=self.timeout)
        if self.provider == "gemini":
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            return genai.GenerativeModel(self.model)
        if self.provider == "ollama":
            # Ollama exposes an OpenAI-compatible API locally — no key needed
            from openai import OpenAI
            return OpenAI(base_url=_OLLAMA_BASE, api_key="ollama", timeout=self.timeout)
        if self.provider == "demo":
            return None  # DemoLLMClient overrides generate(); _client unused
        raise ValueError(f"Unsupported LLM provider: {self.provider!r}")

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        response_schema: dict | None = None,
    ) -> str | dict | list:
        json_mode = response_schema is not None
        json_instruction = "\n\nReturn only valid JSON, no markdown or extra text." if json_mode else ""

        for attempt in range(2):
            try:
                raw = self._call(prompt + json_instruction, system, json_mode)
                if json_mode:
                    return parse_json_response(raw)
                return raw
            except Exception:
                if attempt == 1:
                    raise
                time.sleep(2)

    def _call(self, prompt: str, system: str | None, json_mode: bool) -> str:
        if self.provider in ("openai", "ollama"):
            return self._openai(prompt, system, json_mode)
        if self.provider == "anthropic":
            return self._anthropic(prompt, system)
        if self.provider == "gemini":
            return self._gemini(prompt, system)
        raise RuntimeError("unreachable")

    def _openai(self, prompt: str, system: str | None, json_mode: bool) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        kwargs: dict = {"model": self.model, "messages": messages}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = self._client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content

    def _anthropic(self, prompt: str, system: str | None) -> str:
        kwargs: dict = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        resp = self._client.messages.create(**kwargs)
        return resp.content[0].text

    def _gemini(self, prompt: str, system: str | None) -> str:
        full = f"{system}\n\n{prompt}" if system else prompt
        return self._client.generate_content(full).text


class MockLLMClient(LLMClient):
    """Drop-in replacement for unit tests — returns configurable canned responses."""

    def __init__(self, responses: list[str | dict] | None = None) -> None:
        self.provider = "mock"
        self._responses = list(responses or [])
        self._index = 0

    def generate(self, prompt: str, system=None, response_schema=None):
        if not self._responses:
            return {} if response_schema is not None else ""
        result = self._responses[self._index % len(self._responses)]
        self._index += 1
        return result


class DemoLLMClient(LLMClient):
    """
    Generates realistic-looking content from the prompt without any API call.
    Set AI_TUTOR_LLM_PROVIDER=demo to use this — no API key required.

    Useful for UI development, demos, and CI pipelines.
    """

    def __init__(self) -> None:
        self.provider = "demo"
        self._client = None

    def generate(self, prompt: str, system=None, response_schema=None):
        if response_schema is None:
            return "Demo response."
        p = prompt.lower()
        if "decompose" in p or "sub-topic" in p:
            return self._topics(prompt)
        if "enrich" in p or "learner-friendly" in p:
            return self._enriched(prompt)
        if "diagram" in p and "mermaid" in p:
            return self._diagrams(prompt)
        if "comprehension" in p or "check your understanding" in p:
            return self._inline_questions(prompt)
        if "exam-quality" in p or "assessment question" in p:
            return self._quiz_questions(prompt)
        if "classify" in p and "difficulty" in p:
            return self._classify(prompt)
        return {}

    # --- helpers -----------------------------------------------------------

    @staticmethod
    def _extract_topic(prompt: str) -> str:
        m = re.search(r"Topic:\s*(.+)", prompt)
        return m.group(1).strip() if m else "Core Concept"

    @staticmethod
    def _extract_section_ids(prompt: str) -> list[str]:
        return re.findall(r"section_id:\s*([\w-]+)", prompt)

    def _topics(self, prompt: str) -> dict:
        section_ids = self._extract_section_ids(prompt)
        title_matches = re.findall(r"##\s+(.+)", prompt)
        topic_titles = title_matches[:6] or [
            "Introduction & Background",
            "Core Principles",
            "Key Mechanisms",
            "Practical Applications",
            "Summary & Next Steps",
        ]
        chunk = max(1, len(section_ids) // len(topic_titles)) if section_ids else 1
        topics = []
        for i, title in enumerate(topic_titles):
            start = i * chunk
            sids = section_ids[start : start + chunk] if section_ids else []
            topics.append({"title": title, "summary": f"Overview of {title.lower()}.", "source_section_ids": sids})
        return {"topics": topics}

    def _enriched(self, prompt: str) -> dict:
        topic = self._extract_topic(prompt)
        return {
            "content_html": (
                f"## {topic}\n\n"
                "This topic covers foundational concepts that underpin the subject area. "
                "Understanding these ideas allows learners to build a solid mental model "
                "before tackling more advanced material.\n\n"
                "### Key Ideas\n\n"
                "- **Concept A** — the primary mechanism driving the system\n"
                "- **Concept B** — how components interact with each other\n"
                "- **Concept C** — real-world implications and trade-offs\n\n"
                "### Key Definitions\n\n"
                "**Term**: A precise description of the core element in this domain.\n\n"
                "> **Analogy**: Think of it like a postal system — each component has a "
                "specific role, and the whole only works when they cooperate."
            ),
            "key_takeaways": [
                f"{topic} is built on a small set of core principles.",
                "Understanding the relationships between components is more important than memorising details.",
                "Practical application reinforces theoretical knowledge.",
            ],
        }

    def _diagrams(self, prompt: str) -> dict:
        topic = self._extract_topic(prompt)
        return {
            "diagrams": [
                {
                    "caption": f"Overview of {topic}",
                    "mermaid_code": (
                        "graph TD\n"
                        f"    A[{topic}] --> B[Component 1]\n"
                        "    A --> C[Component 2]\n"
                        "    B --> D[Output A]\n"
                        "    C --> D\n"
                        "    D --> E[Final Result]"
                    ),
                }
            ]
        }

    def _inline_questions(self, prompt: str) -> dict:
        topic = self._extract_topic(prompt)
        return {
            "questions": [
                {
                    "question_text": f"Which of the following best describes the primary purpose of {topic}?",
                    "question_type": "single_choice",
                    "options": [
                        "To provide a structured framework for understanding",
                        "To eliminate the need for further study",
                        "To replace all existing approaches",
                        "To introduce unnecessary complexity",
                    ],
                    "correct_answers": [0],
                    "explanation": "The main goal is to provide a structured framework that aids understanding.",
                },
                {
                    "question_text": f"Which statements about {topic} are correct? (select all that apply)",
                    "question_type": "multiple_choice",
                    "options": [
                        "It relies on well-defined components",
                        "It works in isolation without any dependencies",
                        "Practical application deepens understanding",
                        "It cannot be applied to real-world problems",
                    ],
                    "correct_answers": [0, 2],
                    "explanation": "Well-defined components and practical application are hallmarks of this topic.",
                },
            ]
        }

    def _quiz_questions(self, prompt: str) -> dict:
        topic = self._extract_topic(prompt)
        base = [
            {
                "question_text": f"What is the primary function of {topic}?",
                "question_type": "single_choice",
                "options": ["Organising information", "Storing data permanently", "Transmitting signals", "Reducing complexity"],
                "correct_answers": [0],
                "explanation": "Its primary role is to organise and structure information.",
                "difficulty": "easy",
            },
            {
                "question_text": f"Which component is most central to {topic}?",
                "question_type": "single_choice",
                "options": ["Core mechanism", "Peripheral module", "External API", "Cache layer"],
                "correct_answers": [0],
                "explanation": "The core mechanism drives the entire system.",
                "difficulty": "easy",
            },
            {
                "question_text": f"How does {topic} handle conflicts between components?",
                "question_type": "single_choice",
                "options": ["Through a defined resolution protocol", "By ignoring them", "By restarting", "Randomly"],
                "correct_answers": [0],
                "explanation": "A defined resolution protocol ensures consistency.",
                "difficulty": "medium",
            },
            {
                "question_text": f"Which of the following are trade-offs when using {topic}? (select all)",
                "question_type": "multiple_choice",
                "options": ["Increased clarity", "Higher initial complexity", "Reduced flexibility", "Better maintainability"],
                "correct_answers": [0, 1, 3],
                "explanation": "Clarity and maintainability improve, but initial complexity rises.",
                "difficulty": "medium",
            },
            {
                "question_text": f"In an advanced scenario, how would {topic} behave under high load?",
                "question_type": "single_choice",
                "options": ["Degrade gracefully", "Fail immediately", "Ignore all requests", "Restart automatically"],
                "correct_answers": [0],
                "explanation": "Graceful degradation is a design goal for robust systems.",
                "difficulty": "hard",
            },
        ]
        return {"questions": base}

    def _classify(self, prompt: str) -> dict:
        ids = re.findall(r"\[([^\]]+)\]", prompt)
        difficulties = ["easy", "medium", "hard"]
        return {
            "classifications": [
                {"question_id": qid, "difficulty": difficulties[i % 3]}
                for i, qid in enumerate(ids)
            ]
        }
