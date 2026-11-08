"""OpenTelemetry tracing with a no-op fallback, so agent code can always wrap work in ``span``."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from stubbleos.core.config import Settings

_tracer: Any | None = None


def setup_tracing(settings: Settings) -> bool:
    """Enable tracing if configured and the SDK is importable. Returns True when active."""
    global _tracer  # noqa: PLW0603
    if not settings.otel_enabled:
        _tracer = None
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
    except ImportError:
        _tracer = None
        return False
    provider = TracerProvider(resource=Resource.create({"service.name": "stubbleos"}))
    # Exporter wiring (OTLP) is added with the observability work ; spans are
    # created and propagated now so instrumentation points exist from day one.
    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer("stubbleos")
    return True


@contextmanager
def span(name: str, **attributes: str | int | float | bool) -> Iterator[Any]:
    if _tracer is None:
        yield None
        return
    with _tracer.start_as_current_span(name) as s:
        for key, value in attributes.items():
            s.set_attribute(key, value)
        yield s
