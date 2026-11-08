"""Anthropic Messages API adapter."""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel, SecretStr

from stubbleos.core.metrics import LLM_CALLS
from stubbleos.core.telemetry import span
from stubbleos.llm.base import (
    LLMError,
    LLMRequest,
    LLMResponse,
    LLMUsage,
    UsageMeter,
    generate_structured_via_text,
)

T = TypeVar("T", bound=BaseModel)


class AnthropicLLM:
    provider = "anthropic"

    def __init__(
        self,
        *,
        api_key: SecretStr,
        model: str,
        timeout_s: float = 30.0,
        max_retries: int = 3,
        client: Any | None = None,
    ) -> None:
        self.model = model
        self.meter = UsageMeter()
        if client is None:
            import anthropic

            # Retries and backoff are handled by the SDK; timeout applies per request.
            client = anthropic.AsyncAnthropic(
                api_key=api_key.get_secret_value(), timeout=timeout_s, max_retries=max_retries
            )
        self._client: Any = client

    async def generate(self, request: LLMRequest) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": request.max_tokens,
            "messages": [{"role": m.role.value, "content": m.content} for m in request.messages],
        }
        if request.system:
            kwargs["system"] = request.system
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        with span("llm.generate", provider=self.provider, purpose=request.purpose):
            try:
                resp = await self._client.messages.create(**kwargs)
            except Exception as exc:
                LLM_CALLS.labels(provider=self.provider, outcome="error").inc()
                raise LLMError(f"{type(exc).__name__}: {exc}") from exc
        LLM_CALLS.labels(provider=self.provider, outcome="ok").inc()
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        usage = LLMUsage(
            input_tokens=getattr(resp.usage, "input_tokens", 0),
            output_tokens=getattr(resp.usage, "output_tokens", 0),
        )
        self.meter.record(usage)
        return LLMResponse(text=text, usage=usage, model=self.model, provider=self.provider)

    async def generate_structured(self, request: LLMRequest, schema: type[T]) -> T:
        return await generate_structured_via_text(self, request, schema)
