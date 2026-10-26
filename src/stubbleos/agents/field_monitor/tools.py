"""Mock tools for Field Monitor agent."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool


@tool
def sentinel2_harvest_detector_mock(field_id_str: str) -> dict[str, Any]:
    """Mock satellite harvest detector checking NDVI drops."""
    return {
        "field_id": field_id_str,
        "harvest_detected": True,
        "confidence": 0.94,
        "sensor": "Sentinel-2 L2A",
    }


@tool
def firms_thermal_anomaly_detector_mock(field_id_str: str) -> dict[str, Any]:
    """Mock FIRMS MODIS/VIIRS thermal anomaly fire detector."""
    return {
        "field_id": field_id_str,
        "fire_detected": False,
        "brightness_kelvin": 305.2,
        "confidence": 0.88,
    }


def create_field_monitor_tools() -> list[Any]:
    return [sentinel2_harvest_detector_mock, firms_thermal_anomaly_detector_mock]
