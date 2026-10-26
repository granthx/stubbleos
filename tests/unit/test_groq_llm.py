from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel, SecretStr

from stubbleos.core.config import Settings
from stubbleos.llm.base import LLMError, LLMRequest
from stubbleos.llm.factory import build_llm
from stubbleos.llm.groq_client import GroqLLM


class SampleOutput(BaseModel):
    summary: str
    count: int


def _mock_completion(content: str, prompt_tokens: int = 10, completion_tokens: int = 20) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


async def test_groq_generate_success() -> None:
    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = _mock_completion("Hello from Groq")

    llm = GroqLLM(
        api_key=SecretStr("gsk-test"),
        model="llama-3.3-70b-versatile",
        client=mock_client,
    )
    req = LLMRequest.simple("test message", system="You are an assistant")
    res = await llm.generate(req)

    assert res.text == "Hello from Groq"
    assert res.provider == "groq"
    assert res.model == "llama-3.3-70b-versatile"
    assert res.usage.input_tokens == 10
    assert res.usage.output_tokens == 20
    assert llm.meter.input_tokens == 10
    assert llm.meter.output_tokens == 20
    assert llm.meter.calls == 1

    mock_client.chat.completions.create.assert_awaited_once()
    call_kwargs = mock_client.chat.completions.create.await_args.kwargs
    assert call_kwargs["messages"][0] == {"role": "system", "content": "You are an assistant"}
    assert call_kwargs["messages"][1] == {"role": "user", "content": "test message"}


async def test_groq_generate_structured_success() -> None:
    mock_client = AsyncMock()
    mock_client.chat.completions.create.return_value = _mock_completion('{"summary": "cleared", "count": 42}')

    llm = GroqLLM(
        api_key=SecretStr("gsk-test"),
        model="llama-3.3-70b-versatile",
        client=mock_client,
    )
    req = LLMRequest.simple("give summary")
    structured = await llm.generate_structured(req, SampleOutput)

    assert structured.summary == "cleared"
    assert structured.count == 42


async def test_groq_generate_error_raises_llm_error() -> None:
    mock_client = AsyncMock()
    mock_client.chat.completions.create.side_effect = RuntimeError("API unavailable")

    llm = GroqLLM(
        api_key=SecretStr("gsk-test"),
        model="llama-3.3-70b-versatile",
        client=mock_client,
    )
    with pytest.raises(LLMError, match="RuntimeError: API unavailable"):
        await llm.generate(LLMRequest.simple("hello"))


def test_factory_builds_groq_llm() -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        llm_provider="auto",
        groq_api_key="gsk-test",
    )
    client = build_llm(settings)
    assert isinstance(client, GroqLLM)
    assert client.provider == "groq"
    assert client.model == "llama-3.3-70b-versatile"
