"""LLM interface, request/response types and structured-output helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from stubbleos.core.types import FrozenModel

T = TypeVar("T", bound=BaseModel)


class Role(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(FrozenModel):
    role: Role
    content: str


class LLMRequest(FrozenModel):
    messages: tuple[ChatMessage, ...]
    system: str | None = None
    max_tokens: int = 1024
    temperature: float | None = None
    purpose: str = "unspecified"  # attribution for tracing / coordination-overhead metrics
    prompt_ref: str | None = None  # "name@vN" from the prompt registry

    @classmethod
    def simple(cls, user_text: str, *, system: str | None = None, **kwargs: object) -> LLMRequest:
        return cls(
            messages=(ChatMessage(role=Role.USER, content=user_text),),
            system=system,
            **kwargs,
        )

    def full_text(self) -> str:
        return "\n".join(m.content for m in self.messages)


class LLMUsage(FrozenModel):
    input_tokens: int = 0
    output_tokens: int = 0


class LLMResponse(FrozenModel):
    text: str
    usage: LLMUsage = LLMUsage()
    model: str = ""
    provider: str = ""


@dataclass
class UsageMeter:
    """Accumulates calls and tokens; feeds the 'LLM calls per plan' overhead metric."""

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def record(self, usage: LLMUsage) -> None:
        self.calls += 1
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens


class LLMError(RuntimeError):
    pass


class LLMStructuredOutputError(LLMError):
    pass


class LLMClient(Protocol):
    provider: str
    model: str
    meter: UsageMeter

    async def generate(self, request: LLMRequest) -> LLMResponse: ...

    async def generate_structured(self, request: LLMRequest, schema: type[T]) -> T: ...


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def extract_json(text: str) -> str:
    """Strip markdown fences and surrounding prose; return the outermost JSON object."""
    stripped = _FENCE_RE.sub("", text.strip())
    start, end = stripped.find("{"), stripped.rfind("}")
    if start == -1 or end <= start:
        raise LLMStructuredOutputError("no JSON object found in model output")
    return stripped[start : end + 1]


def parse_structured(text: str, schema: type[T]) -> T:
    try:
        return schema.model_validate_json(extract_json(text))
    except ValidationError as exc:
        raise LLMStructuredOutputError(f"output failed {schema.__name__} validation: {exc}") from exc
    except json.JSONDecodeError as exc:  # pragma: no cover - model_validate_json wraps most cases
        raise LLMStructuredOutputError(f"invalid JSON: {exc}") from exc


def schema_instruction(schema: type[BaseModel]) -> str:
    return (
        "Respond with ONLY a single JSON object (no prose, no markdown fences) that conforms to this "
        f"JSON Schema:\n{json.dumps(schema.model_json_schema(), separators=(',', ':'))}"
    )


async def generate_structured_via_text(
    client: LLMClient, request: LLMRequest, schema: type[T], *, max_attempts: int = 2
) -> T:
    """Prompt-based structured output with validation and error-feedback retry.

    Never trusts model output: the result is always a validated Pydantic instance or an error.
    """
    instruction = schema_instruction(schema)
    system = f"{request.system}\n\n{instruction}" if request.system else instruction
    req = request.model_copy(update={"system": system})
    last_error: LLMStructuredOutputError | None = None
    for _ in range(max_attempts):
        response = await client.generate(req)
        try:
            return parse_structured(response.text, schema)
        except LLMStructuredOutputError as exc:
            last_error = exc
            req = req.model_copy(
                update={
                    "messages": (
                        *req.messages,
                        ChatMessage(role=Role.ASSISTANT, content=response.text),
                        ChatMessage(
                            role=Role.USER,
                            content=f"That reply was invalid ({exc}). Return only the corrected JSON object.",
                        ),
                    )
                }
            )
    raise LLMStructuredOutputError(
        f"no valid {schema.__name__} after {max_attempts} attempts"
    ) from last_error
