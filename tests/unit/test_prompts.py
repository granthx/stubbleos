import pytest

from stubbleos.core.types import Language
from stubbleos.llm.prompts import PromptError, PromptNotFound, PromptRegistry, PromptTemplate


def reg() -> PromptRegistry:
    r = PromptRegistry()
    r.register(PromptTemplate(name="offer", version=1, template="Offer $price for $tonnes t"))
    r.register(PromptTemplate(name="offer", version=2, template='{"p": "$price"} t=$tonnes'))
    r.register(PromptTemplate(name="offer", version=2, language=Language.HINDI, template="HI $price $tonnes"))
    return r


def test_latest_version_by_default_and_json_braces_are_safe() -> None:
    out = reg().render("offer", price="100", tonnes="2")
    assert out.ref == "offer@v2"
    assert out.text == '{"p": "100"} t=2'


def test_language_specific_then_fallback() -> None:
    r = reg()
    assert r.render("offer", language=Language.HINDI, price="1", tonnes="2").ref == "offer@v2:hi"
    assert r.render("offer", language=Language.PUNJABI, price="1", tonnes="2").ref == "offer@v2"


def test_pinned_version() -> None:
    assert reg().render("offer", version=1, price="1", tonnes="2").text == "Offer 1 for 2 t"


def test_strict_variables() -> None:
    r = reg()
    with pytest.raises(PromptError):
        r.render("offer", price="1")
    with pytest.raises(PromptError):
        r.render("offer", price="1", tonnes="2", typo="x")


def test_duplicates_invalid_and_missing() -> None:
    r = reg()
    with pytest.raises(PromptError):
        r.register(PromptTemplate(name="offer", version=1, template="again"))
    with pytest.raises(PromptError):
        r.register(PromptTemplate(name="bad", version=1, template="cost $"))
    with pytest.raises(PromptNotFound):
        r.get("absent")
