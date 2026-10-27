"""LangChain tools for Field Monitor agent."""

from __future__ import annotations

import uuid
from typing import Any

from langchain_core.tools import tool

from stubbleos.agents.field_monitor.logic import (
    build_field_events,
    detect_field_states,
    evaluate_field_observation,
)
from stubbleos.agents.field_monitor.schemas import (
    FieldMonitorInput,
    FieldObservation,
    FieldObservationRequest,
)
from stubbleos.core.events import EventBus
from stubbleos.data.repositories import ApprovalRepository


@tool
def sentinel2_harvest_detector_mock(field_id_str: str) -> dict[str, Any]:
    """Analyzes Sentinel-2 optical imagery to detect crop harvest and residue presence."""
    return {
        "field_id": field_id_str,
        "harvest_detected": True,
        "ndvi_drop": 0.38,
        "current_ndvi": 0.28,
        "current_bsi": -0.05,
        "cloud_cover_pct": 2.5,
    }


@tool
def firms_thermal_anomaly_detector_mock(field_id_str: str) -> dict[str, Any]:
    """Checks NASA FIRMS VIIRS active fire hotspots over the field polygon."""
    return {
        "field_id": field_id_str,
        "thermal_anomaly_detected": False,
        "confidence": "nominal",
        "brightness_kelvin": 305.2,
    }


@tool
def evaluate_field_observation_tool(req_dict: dict[str, Any]) -> dict[str, Any]:
    """Classifies a field based on optical NDVI/BSI indices and thermal FIRMS hits."""
    req = FieldObservationRequest.model_validate(req_dict)
    res = evaluate_field_observation(req)
    return res.model_dump()


@tool
def batch_evaluate_fields_tool(input_dict: dict[str, Any]) -> dict[str, Any]:
    """Runs batch evaluation of multiple fields across a district."""
    inp = FieldMonitorInput.model_validate(input_dict)
    out = detect_field_states(inp)
    return out.model_dump()


@tool
async def route_field_to_approval_tool(
    field_id: str,
    reason: str,
    confidence: float,
    detected_state: str,
    approval_repo: ApprovalRepository | None = None,
) -> dict[str, Any]:
    """Submits an ambiguous or low-confidence field state transition to the human coordinator queue."""
    f_uuid = uuid.UUID(field_id)
    if approval_repo is not None:
        approval = approval_repo.create(
            kind="field_state_change",
            subject_type="field",
            subject_id=f_uuid,
            reason=reason,
            requested_by="field_monitor",
            confidence=confidence,
            payload={"field_id": field_id, "detected_state": detected_state},
        )
        return {"status": "created", "approval_id": str(approval.id)}
    return {"status": "mocked", "approval_id": str(uuid.uuid4())}


@tool
async def publish_field_events_tool(
    res_dict: dict[str, Any],
    event_bus: EventBus | None = None,
) -> dict[str, Any]:
    """Publishes FieldStateChanged or BurnDetected domain events on the event bus."""
    res = FieldObservation.model_validate(res_dict)
    events = build_field_events(res)
    emitted_count = 0
    if event_bus is not None:
        for ev in events:
            await event_bus.emit(ev, source="field_monitor")
            emitted_count += 1
    return {"status": "published", "count": emitted_count}


def create_field_monitor_tools(
    approval_repo: ApprovalRepository | None = None,
    event_bus: EventBus | None = None,
) -> list[Any]:
    """Factory to create Field Monitor tools for agent and graph execution."""
    return [
        sentinel2_harvest_detector_mock,
        firms_thermal_anomaly_detector_mock,
    ]
