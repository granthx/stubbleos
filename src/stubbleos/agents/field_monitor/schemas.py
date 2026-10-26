"""Typed contracts for Field Monitor agent (Phase 4 skeleton, full in Phase 5)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from stubbleos.core.types import FieldState


class FieldObservation(BaseModel):
    """Satellite or sensor observation of a farm field."""

    model_config = ConfigDict(extra="forbid")

    field_id: UUID
    timestamp: datetime
    detected_state: FieldState
    confidence: float = Field(..., ge=0.0, le=1.0)
    thermal_anomaly_detected: bool = False
    source: str = "sentinel2_mock"


class FieldMonitorInput(BaseModel):
    """Input query to inspect field states in a district."""

    model_config = ConfigDict(extra="forbid")

    district: str
    field_ids: list[UUID]
    observation_window_hours: float = 24.0


class FieldMonitorOutput(BaseModel):
    """Aggregated satellite sensing output."""

    model_config = ConfigDict(extra="forbid")

    observations: list[FieldObservation]
    newly_harvested_count: int
    burn_detected_count: int


class FieldMonitorState(BaseModel):
    """LangGraph state for Field Monitor agent."""

    model_config = ConfigDict(extra="forbid")

    input: FieldMonitorInput
    output: FieldMonitorOutput | None = None
    status: str = "initialized"
