"""Failure mode tests for components and agents."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from stubbleos.agents.field_monitor.schemas import (
    FieldObservationRequest,
)
from stubbleos.agents.mrv.schemas import MrvInput
from stubbleos.agents.weather_window.schemas import WeatherWindowInput
from stubbleos.core.retry import RetryExhausted
from stubbleos.geo.client import CachingGeoClient


def test_failure_mode_field_monitor_bad_coordinates() -> None:
    """Field Monitor failure mode: Malformed polygon coordinates or extra keys rejected."""
    with pytest.raises(ValidationError):
        FieldObservationRequest(
            field_id=uuid.uuid4(),
            extra_illegal_key="fail",  # type: ignore[call-arg]
        )


def test_failure_mode_weather_window_invalid_date_ordering() -> None:
    """Weather Window failure mode: Invalid date format rejected."""
    with pytest.raises(ValidationError):
        WeatherWindowInput(
            district="Sangrur",
            start_date="not_a_date",  # type: ignore[arg-type]
            end_date="not_a_date",  # type: ignore[arg-type]
        )


def test_failure_mode_mrv_negative_or_zero_area() -> None:
    """MRV failure mode: Non-positive area rejected."""
    with pytest.raises(ValidationError):
        MrvInput(field_id=uuid.uuid4(), area_acres=0.0)

    with pytest.raises(ValidationError):
        MrvInput(field_id=uuid.uuid4(), area_acres=-10.0)


@pytest.mark.asyncio
async def test_failure_mode_missing_fixture_raises_error() -> None:
    """Geo client failure mode: Missing offline fixture raises FileNotFoundError."""
    client = CachingGeoClient()
    with pytest.raises(FileNotFoundError):
        client.load_fixture("non_existent_fixture.json")


@pytest.mark.asyncio
async def test_failure_mode_remote_failure_without_fixture_propagates() -> None:
    """Geo client failure mode: Remote failure without fallback fixture propagates exception."""
    client = CachingGeoClient()
    with (
        patch("httpx.AsyncClient.get", side_effect=TimeoutError("Network down")),
        pytest.raises(RetryExhausted),
    ):
        await client.get_json("https://broken.api/v1", fixture_fallback_name=None)
