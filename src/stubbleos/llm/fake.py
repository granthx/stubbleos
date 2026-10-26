"""Deterministic scripted LLM for tests and simulation. No network, no randomness."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Self, TypeVar

from pydantic import BaseModel

from stubbleos.llm.base import (
    LLMError,
    LLMRequest,
    LLMResponse,
    LLMStructuredOutputError,
    LLMUsage,
    UsageMeter,
    parse_structured,
)

T = TypeVar("T", bound=BaseModel)

Matcher = str | re.Pattern[str] | Callable[[LLMRequest], bool]
FakeResponse = str | BaseModel | dict[str, Any]
ResponseSpec = FakeResponse | Callable[[LLMRequest], FakeResponse]


class FakeLLMNoResponseError(LLMError):
    """Raised when nothing is scripted for a request. Failing loudly beats silently inventing text."""


FakeLLMNoResponse = FakeLLMNoResponseError


@dataclass
class _Rule:
    matcher: Matcher
    response: ResponseSpec

    def matches(self, request: LLMRequest) -> bool:
        if isinstance(self.matcher, str):
            return self.matcher in request.full_text()
        if isinstance(self.matcher, re.Pattern):
            return self.matcher.search(request.full_text()) is not None
        return self.matcher(request)


@dataclass
class FakeLLM:
    """Resolution order per call: FIFO queue, then rules in insertion order, then ``default``."""

    default: FakeResponse | None = None
    provider: str = "fake"
    model: str = "fake-1"
    calls: list[LLMRequest] = field(default_factory=list)
    meter: UsageMeter = field(default_factory=UsageMeter)
    _queue: list[ResponseSpec] = field(default_factory=list)
    _rules: list[_Rule] = field(default_factory=list)

    def queue(self, *responses: ResponseSpec) -> Self:
        self._queue.extend(responses)
        return self

    def when(self, matcher: Matcher, response: ResponseSpec) -> Self:
        self._rules.append(_Rule(matcher, response))
        return self

    def _resolve(self, request: LLMRequest) -> FakeResponse:
        spec: ResponseSpec | None = None
        if self._queue:
            spec = self._queue.pop(0)
        else:
            for rule in self._rules:
                if rule.matches(request):
                    spec = rule.response
                    break
        if spec is None:
            spec = self.default
        if spec is None:
            raise FakeLLMNoResponse(
                f"no scripted response for purpose={request.purpose!r}: {request.full_text()[:120]!r}"
            )
        if callable(spec) and not isinstance(spec, BaseModel):
            return spec(request)
        return spec

    @staticmethod
    def _to_text(resp: FakeResponse) -> str:
        if isinstance(resp, str):
            return resp
        if isinstance(resp, BaseModel):
            return resp.model_dump_json()
        return json.dumps(resp, default=str)

    def _record(self, request: LLMRequest, text: str) -> LLMResponse:
        self.calls.append(request)
        usage = LLMUsage(
            input_tokens=max(1, len(request.full_text()) // 4), output_tokens=max(1, len(text) // 4)
        )
        self.meter.record(usage)
        return LLMResponse(text=text, usage=usage, model=self.model, provider=self.provider)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        return self._record(request, self._to_text(self._resolve(request)))

    async def generate_structured(self, request: LLMRequest, schema: type[T]) -> T:
        resolved = self._resolve(request)
        self._record(request, self._to_text(resolved))
        if isinstance(resolved, schema):
            return resolved
        if isinstance(resolved, BaseModel):
            return _validate(schema, resolved.model_dump())
        if isinstance(resolved, dict):
            return _validate(schema, resolved)
        return parse_structured(resolved, schema)


def _validate(schema: type[T], data: dict[str, Any]) -> T:
    try:
        return schema.model_validate(data)
    except Exception as exc:
        raise LLMStructuredOutputError(f"scripted response failed {schema.__name__}: {exc}") from exc
