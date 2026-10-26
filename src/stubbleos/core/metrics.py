"""Prometheus metrics shared across modules."""

from __future__ import annotations

from prometheus_client import Counter

EVENTS_PUBLISHED = Counter("stubbleos_events_published_total", "Events published on the bus", ["event_type"])
HANDLER_ERRORS = Counter("stubbleos_event_handler_errors_total", "Event handler failures", ["handler"])
LLM_CALLS = Counter("stubbleos_llm_calls_total", "LLM calls", ["provider", "outcome"])
