"""Typed settings. All secrets come from the environment; nothing is hard-coded."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal, Self

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_ONLY_SALT = "dev-only-salt-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="STUBBLEOS_",
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
    )

    env: Literal["dev", "test", "prod"] = "dev"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_json: bool = False

    database_url: str = "postgresql+psycopg://stubbleos:stubbleos@localhost:5432/stubbleos"
    redis_url: str = "redis://localhost:6379/0"

    # LLM: "auto" = Groq if key present, else Anthropic if key present, otherwise FakeLLM.
    llm_provider: Literal["auto", "groq", "anthropic", "fake"] = "auto"
    llm_model: str = "llama-3.3-70b-versatile"
    llm_timeout_s: float = Field(default=30.0, gt=0)
    llm_max_retries: int = Field(default=3, ge=0, le=10)
    groq_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("STUBBLEOS_GROQ_API_KEY", "GROQ_API_KEY"),
    )
    anthropic_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("STUBBLEOS_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"),
    )

    # Privacy
    pseudonym_salt: SecretStr = SecretStr(DEV_ONLY_SALT)

    # Outreach policy (IST wall-clock hours; enforced by the Policy Guard in Phase 4)
    contact_hours_start: int = Field(default=8, ge=0, le=23)
    contact_hours_end: int = Field(default=19, ge=1, le=24)
    whatsapp_enabled: bool = False  # real delivery is off unless explicitly enabled

    # Observability
    otel_enabled: bool = False
    otel_endpoint: str | None = None

    # Geo & Remote Sensing (Phase 5)
    stac_api_url: str = "https://earth-search.aws.element84.com/v1"
    firms_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("STUBBLEOS_FIRMS_API_KEY", "FIRMS_API_KEY"),
    )
    firms_api_url: str = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
    open_meteo_url: str = "https://api.open-meteo.com/v1/forecast"
    geo_cache_ttl_seconds: int = Field(default=86400, ge=60)
    geo_client_timeout_s: float = Field(default=10.0, gt=0)
    geo_client_max_retries: int = Field(default=3, ge=0, le=10)
    offline_fixtures_dir: str = "tests/fixtures"

    # Field Monitor Thresholds (Phase 5)
    ndvi_harvest_drop_threshold: float = Field(default=0.25, ge=0.0, le=1.0)
    bsi_cleared_threshold: float = Field(default=0.15, ge=-1.0, le=1.0)
    firms_confidence_threshold: float = Field(default=50.0, ge=0.0, le=100.0)
    field_monitor_min_confidence_approval: float = Field(default=0.70, ge=0.0, le=1.0)

    # Weather & Window Thresholds (Phase 5)
    max_workable_rain_mm: float = Field(default=2.0, ge=0.0)
    max_workable_wind_kmh: float = Field(default=35.0, ge=0.0)
    max_soil_moisture_index: float = Field(default=0.40, ge=0.0, le=1.0)
    replan_rain_delta_threshold_mm: float = Field(default=5.0, ge=0.0)

    # Simulation
    simulation_default_seed: int = 20260101

    @model_validator(mode="after")
    def _validate(self) -> Self:
        if self.contact_hours_start >= self.contact_hours_end:
            raise ValueError("contact_hours_start must be < contact_hours_end")
        if self.llm_provider == "groq" and self.groq_api_key is None:
            raise ValueError("llm_provider='groq' requires an API key")
        if self.llm_provider == "anthropic" and self.anthropic_api_key is None:
            raise ValueError("llm_provider='anthropic' requires an API key")
        if self.env == "prod":
            if self.pseudonym_salt.get_secret_value() == DEV_ONLY_SALT:
                raise ValueError("prod requires STUBBLEOS_PSEUDONYM_SALT to be set")
            if self.llm_provider == "fake":
                raise ValueError("prod must not run with the fake LLM")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
