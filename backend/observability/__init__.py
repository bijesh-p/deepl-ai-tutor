"""LLM observability: OTEL tracing to Arize Phoenix + DeepEval quality metrics."""
from __future__ import annotations

from backend.observability.tracer import get_tracer, setup_tracing

__all__ = ["setup_tracing", "get_tracer"]
