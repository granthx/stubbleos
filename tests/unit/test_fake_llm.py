import re

import pytest
from pydantic import BaseModel

from stubbleos.llm.base import (
    LLMRequest,
    LLMStructuredOutputError,
    extract_json,
    generate_structured_via_text,
)
from stubbleos.llm.fake import FakeLLM, FakeLLMNoResponse


class Offer(BaseModel):
    price: int
    accept: bool


def req(text: str, purpose: str = "t") -> LLMRequest:
    return LLMRequest.simple(text, purpose=purpose)


async def test_queue_then_rules_then_default() -> None:
    llm = FakeLLM(default="dflt").queue("first").when("rain", "umbrella").when(re.compile(r"^hi"), "hello")
    assert (await llm.generate(req("anything"))).text == "first"
    assert (await llm.generate(req("will it rain"))).text == "umbrella"
    assert (await llm.generate(req("hi there"))).text == "hello"
    assert (await llm.generate(req("zzz"))).text == "dflt"
    assert len(llm.calls) == 4
    assert llm.meter.calls == 4


async def test_callable_rule_and_callable_response() -> None:
    llm = FakeLLM().when(lambda r: r.purpose == "p", lambda r: f"echo:{r.full_text()}")
    assert (await llm.generate(req("x", purpose="p"))).text == "echo:x"


async def test_no_response_fails_loudly() -> None:
    with pytest.raises(FakeLLMNoResponse):
        await FakeLLM().generate(req("x"))


async def test_structured_from_model_dict_and_json_string() -> None:
    llm = FakeLLM().queue(
        Offer(price=1, accept=True),
        {"price": 2, "accept": False},
        '```json\n{"price": 3, "accept": true}\n```',
    )
    assert (await llm.generate_structured(req("a"), Offer)).price == 1
    assert (await llm.generate_structured(req("b"), Offer)).price == 2
    assert (await llm.generate_structured(req("c"), Offer)).price == 3


async def test_structured_invalid_raises() -> None:
    llm = FakeLLM().queue({"price": "not-a-number"}, "no json here")
    with pytest.raises(LLMStructuredOutputError):
        await llm.generate_structured(req("a"), Offer)
    with pytest.raises(LLMStructuredOutputError):
        await llm.generate_structured(req("b"), Offer)


async def test_text_based_structured_retries_with_feedback() -> None:
    llm = FakeLLM().queue("sorry, I cannot", '{"price": 9, "accept": true}')
    out = await generate_structured_via_text(llm, req("offer?"), Offer, max_attempts=2)
    assert out == Offer(price=9, accept=True)
    assert len(llm.calls) == 2
    assert "JSON Schema" in (llm.calls[0].system or "")
    assert "invalid" in llm.calls[1].messages[-1].content


async def test_text_based_structured_gives_up() -> None:
    llm = FakeLLM(default="nope")
    with pytest.raises(LLMStructuredOutputError):
        await generate_structured_via_text(llm, req("x"), Offer, max_attempts=2)
    assert len(llm.calls) == 2


def test_extract_json_handles_prose_and_fences() -> None:
    assert extract_json('Sure! {"a": 1} hope that helps') == '{"a": 1}'
    with pytest.raises(LLMStructuredOutputError):
        extract_json("no braces")
