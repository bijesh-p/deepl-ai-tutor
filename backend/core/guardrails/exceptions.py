from __future__ import annotations


class GuardrailViolation(Exception):
    """Raised when an LLM call is blocked by a guardrail check.

    `str(exc)` returns the friendly, user-facing `message` — existing error
    UI (`_render_tutor_error`, `_render_failed_state`) just displays
    `str(exc)`, so this is what students/uploaders actually see.
    """

    def __init__(self, category: str, message: str, details: str = ""):
        super().__init__(message)
        self.category = category
        self.message = message
        self.details = details
