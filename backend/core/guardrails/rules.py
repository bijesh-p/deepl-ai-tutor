from __future__ import annotations

import re

# Classic prompt-injection phrasing: instruction-override attempts, fake
# role-marker tags (trying to forge a new conversation turn), and common
# jailbreak keywords. Deliberately full-phrase patterns, not single words —
# "injection" alone would false-positive on legitimate security curriculum
# content (e.g. "Explain how SQL injection attacks work").
_INJECTION_PATTERNS: list[tuple[str, str]] = [
    (r"ignore (all )?(the )?(previous|prior|above|earlier) instructions", "instruction_override"),
    (r"disregard (all )?(the )?(previous|prior|above|earlier) (instructions|prompt|rules)", "instruction_override"),
    (r"forget (everything|all|what) (you('| )?(were|was)|i) (told|said)", "instruction_override"),
    (r"you are now (a|an|no longer)\b", "role_override"),
    (r"new instructions?\s*:", "instruction_override"),
    (r"system prompt\s*:\s*$", "role_override"),
    (r"\bact as (a|an)\b.{0,40}\b(no rules|unfiltered|uncensored|jailbroken)\b", "role_override"),
    (r"\bdan mode\b", "jailbreak_keyword"),
    (r"\bjailbreak\b", "jailbreak_keyword"),
    (r"</?(system|assistant|user)>", "fake_role_marker"),
    (r"^\s*(system|assistant)\s*:", "fake_role_marker"),
    (r"\[/?(system|inst|s)\]", "fake_role_marker"),
    (r"reveal (your|the) (system prompt|instructions)", "prompt_extraction"),
    (r"what (are|is) your (system prompt|instructions)", "prompt_extraction"),
    (r"override (your|the) (guidelines|rules|instructions|programming)", "instruction_override"),
    (r"do anything now", "jailbreak_keyword"),
    (r"pretend (you|that you) (have no|don'?t have) (restrictions|guidelines|rules)", "role_override"),
    (r"\bsudo\b.{0,20}\b(mode|override)\b", "instruction_override"),
]

_COMPILED_INJECTION_PATTERNS = [
    (re.compile(pattern, re.IGNORECASE | re.MULTILINE), label)
    for pattern, label in _INJECTION_PATTERNS
]

# High-precision refusal boilerplate — full phrases, not single words like
# "sorry" or "cannot", to avoid tripping on legitimate tutor content (e.g.
# "I cannot stress enough how important...").
_REFUSAL_PHRASES = [
    "i cannot assist with that",
    "i can't assist with that",
    "i cannot help with that",
    "i'm not able to help with that",
    "i cannot provide that information",
    "as an ai language model, i cannot",
    "i'm sorry, but i can't",
    "i won't be able to help with this request",
]


def check_prompt_injection(text: str) -> str | None:
    """Scan text for classic prompt-injection patterns. Returns the matched
    category label on first hit, else None."""
    if not text:
        return None
    for pattern, label in _COMPILED_INJECTION_PATTERNS:
        if pattern.search(text):
            return label
    return None


def check_output_quality(text: str | None) -> str | None:
    """Generic safety net for string LLM output: empty/whitespace-only
    responses, or near-exact refusal boilerplate. Returns a violation
    reason on hit, else None. Callers should only pass this str results —
    structured tool-call dicts don't carry a meaningful refusal signal."""
    if text is None:
        return None
    if not text.strip():
        return "empty_response"
    lowered = text.lower()
    for phrase in _REFUSAL_PHRASES:
        if phrase in lowered:
            return "refusal_boilerplate"
    return None
