"""Build the configured LLM client."""

from __future__ import annotations

from stubbleos.core.config import Settings
from stubbleos.core.logging import get_logger
from stubbleos.llm.anthropic_client import AnthropicLLM
from stubbleos.llm.base import LLMClient
from stubbleos.llm.fake import FakeLLM
from stubbleos.llm.groq_client import GroqLLM

log = get_logger(__name__)


def build_llm(settings: Settings) -> LLMClient:
    provider = settings.llm_provider
    if provider == "auto":
        if settings.groq_api_key is not None:
            provider = "groq"
        elif settings.anthropic_api_key is not None:
            provider = "anthropic"
        else:
            provider = "fake"
        if provider == "fake":
            log.warning("llm_auto_fallback_to_fake", reason="no API key configured")
    if provider == "groq":
        assert settings.groq_api_key is not None  # noqa: S101  (validated in Settings)
        return GroqLLM(
            api_key=settings.groq_api_key,
            model=settings.llm_model,
            timeout_s=settings.llm_timeout_s,
            max_retries=settings.llm_max_retries,
        )
    if provider == "anthropic":
        assert settings.anthropic_api_key is not None  # noqa: S101  (validated in Settings)
        return AnthropicLLM(
            api_key=settings.anthropic_api_key,
            model=settings.llm_model,
            timeout_s=settings.llm_timeout_s,
            max_retries=settings.llm_max_retries,
        )
    return FakeLLM()
