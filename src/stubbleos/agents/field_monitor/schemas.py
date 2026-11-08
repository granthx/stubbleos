"""Schemas for Field Monitor agent and remote sensing schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from stubbleos.core.clock import IST
from stubbleos.core.types import FieldState


class FieldObservation(BaseModel):
    """Satellite or sensor observation of an agricultural field."""

    model_config = ConfigDict(extra="forbid")

    field_id: UUID
    timestamp: datetime = Field(default_factory=lambda: datetime.now(IST))
    previous_state: FieldState = FieldState.NOT_HARVESTED
    detected_state: FieldState
    confidence: float = Field(..., ge=0.0, le=1.0)
    thermal_anomaly_detected: bool = False
    has_thermal_anomaly: bool = False
    source: str = "sentinel2_l2a"
    ndvi_drop: float = 0.0
    current_bsi: float = 0.0
    requires_approval: bool = False
    approval_reason: str | None = None
    evidence: list[str] = Field(default_factory=list)


# Alias for compatibility
FieldObservationResult = FieldObservation


class FieldObservationRequest(BaseModel):
    """Per-field telemetry input for state evaluation."""

    model_config = ConfigDict(extra="forbid")

    field_id: UUID
    previous_state: FieldState = FieldState.NOT_HARVESTED
    polygon_coordinates: list[tuple[float, float]] = Field(default_factory=list)
    pre_harvest_ndvi: float | None = None
    current_ndvi: float | None = None
    current_bsi: float | None = None
    has_firms_hotspot: bool = False
    firms_confidence_pct: float = 0.0
    source: str = "sentinel2_l2a"
    observation_time: datetime | None = None


class FieldMonitorInput(BaseModel):
    """Batch input query to inspect field states in a district."""

    model_config = ConfigDict(extra="forbid")

    district: str
    field_ids: list[UUID] = Field(default_factory=list)
    fields: list[FieldObservationRequest] = Field(default_factory=list)
    observation_window_hours: float = 24.0


class FieldMonitorOutput(BaseModel):
    """Aggregated satellite sensing output."""

    model_config = ConfigDict(extra="forbid")

    district: str = ""
    observations: list[FieldObservation]
    newly_harvested_count: int = 0
    cleared_count: int = 0
    burn_detected_count: int = 0
    approvals_requested_count: int = 0


class FieldMonitorState(BaseModel):
    """LangGraph state for Field Monitor agent."""

    model_config = ConfigDict(extra="forbid")

    input: FieldMonitorInput
    output: FieldMonitorOutput | None = None
    status: str = "initialized"
    created_approval_ids: list[UUID] = Field(default_factory=list)
    emitted_events_count: int = 0
