"""OTEL tracer setup — sends spans to local Arize Phoenix + optionally LangSmith."""
from __future__ import annotations

import logging
import os

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

_log = logging.getLogger(__name__)
_TRACER_NAME = "ai-tutor"
_setup_done = False


def setup_tracing() -> None:
    """Configure OTEL tracer provider and instrument Anthropic + LangChain SDKs.

    Call once at app startup (app.py). Safe to call multiple times — subsequent
    calls are no-ops.
    """
    global _setup_done
    if _setup_done:
        return
    _setup_done = True

    phoenix_endpoint = os.environ.get(
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "http://localhost:6006/v1/traces",
    )

    provider = TracerProvider()

    # Primary: Arize Phoenix (local, free)
    try:
        otlp_exporter = OTLPSpanExporter(endpoint=phoenix_endpoint)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        _log.info("OTEL → Phoenix at %s", phoenix_endpoint)
    except Exception as exc:
        _log.warning("Phoenix OTLP exporter failed to init: %s", exc)

    # Fallback: console (only if OTEL_CONSOLE_EXPORT=true)
    if os.environ.get("OTEL_CONSOLE_EXPORT", "").lower() == "true":
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)

    # Auto-instrument Anthropic SDK
    try:
        from openinference.instrumentation.anthropic import AnthropicInstrumentor
        AnthropicInstrumentor().instrument(tracer_provider=provider)
        _log.info("Anthropic SDK instrumented")
    except Exception as exc:
        _log.warning("AnthropicInstrumentor failed: %s", exc)

    # Auto-instrument LangChain / LangGraph
    try:
        from openinference.instrumentation.langchain import LangChainInstrumentor
        LangChainInstrumentor().instrument(tracer_provider=provider)
        _log.info("LangChain/LangGraph instrumented")
    except Exception as exc:
        _log.warning("LangChainInstrumentor failed: %s", exc)

    # LangSmith — activated purely via env vars, no extra package needed
    if os.environ.get("LANGCHAIN_TRACING_V2", "").lower() == "true":
        _log.info("LangSmith tracing enabled (project=%s)", os.environ.get("LANGCHAIN_PROJECT", "default"))


def get_tracer() -> trace.Tracer:
    """Return the shared OTEL tracer for manual span creation."""
    return trace.get_tracer(_TRACER_NAME)
