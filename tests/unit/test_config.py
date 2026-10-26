import pytest
from pydantic import ValidationError

from stubbleos.core.config import Settings


def make(**kw: object) -> Settings:
    return Settings(_env_file=None, **kw)  # type: ignore[arg-type]


def test_defaults_are_safe() -> None:
    s = make()
    assert s.llm_provider == "auto"
    assert s.whatsapp_enabled is False
    assert s.otel_enabled is False


def test_prod_requires_real_salt() -> None:
    with pytest.raises(ValidationError):
        make(env="prod", llm_provider="anthropic", anthropic_api_key="k")


def test_prod_rejects_fake_llm() -> None:
    with pytest.raises(ValidationError):
        make(env="prod", pseudonym_salt="x" * 32, llm_provider="fake")


def test_anthropic_requires_key() -> None:
    with pytest.raises(ValidationError):
        make(llm_provider="anthropic")


def test_groq_requires_key() -> None:
    with pytest.raises(ValidationError):
        make(llm_provider="groq")


def test_contact_hours_must_be_ordered() -> None:
    with pytest.raises(ValidationError):
        make(contact_hours_start=19, contact_hours_end=8)


def test_env_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STUBBLEOS_LOG_LEVEL", "DEBUG")
    assert make().log_level == "DEBUG"


def test_unprefixed_anthropic_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    s = make()
    assert s.anthropic_api_key is not None
    assert s.anthropic_api_key.get_secret_value() == "sk-test"
    assert "sk-test" not in repr(s)


def test_unprefixed_groq_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "gsk-test")
    s = make()
    assert s.groq_api_key is not None
    assert s.groq_api_key.get_secret_value() == "gsk-test"
    assert "gsk-test" not in repr(s)
