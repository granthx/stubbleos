"""Pure detection and state classification logic for Field Monitor agent."""

from __future__ import annotations

from datetime import datetime

from stubbleos.agents.field_monitor.schemas import (
    FieldMonitorInput,
    FieldMonitorOutput,
    FieldObservation,
    FieldObservationRequest,
)
from stubbleos.core.clock import IST
from stubbleos.core.config import Settings, get_settings
from stubbleos.core.events import BurnDetected, EventPayload, FieldStateChanged
from stubbleos.core.types import FieldState


def evaluate_field_observation(
    req: FieldObservationRequest,
    settings: Settings | None = None,
) -> FieldObservation:
    """Classifies a field into FieldState based on remote sensing indices and FIRMS hits."""
    cfg = settings or get_settings()
    evidence: list[str] = []
    now = req.observation_time or datetime.now(IST)

    # 1. Thermal fire anomaly check (highest priority: FIRMS)
    if req.has_firms_hotspot and req.firms_confidence_pct >= cfg.firms_confidence_threshold:
        raw_conf = min(1.0, max(0.5, req.firms_confidence_pct / 100.0))
        evidence.append(f"FIRMS thermal hotspot detected with {req.firms_confidence_pct:.1f}% confidence")
        return FieldObservation(
            field_id=req.field_id,
            timestamp=now,
            detected_state=FieldState.BURN_DETECTED,
            confidence=raw_conf,
            thermal_anomaly_detected=True,
            has_thermal_anomaly=True,
            source=req.source,
            ndvi_drop=0.0,
            current_bsi=req.current_bsi or 0.0,
            requires_approval=False,
            evidence=evidence,
        )

    # 2. Vegetation & Soil Index evaluation
    curr_ndvi = req.current_ndvi if req.current_ndvi is not None else 0.70
    pre_ndvi = req.pre_harvest_ndvi if req.pre_harvest_ndvi is not None else 0.70
    ndvi_drop = max(0.0, pre_ndvi - curr_ndvi)
    curr_bsi = req.current_bsi if req.current_bsi is not None else -0.20

    evidence.append(f"NDVI pre={pre_ndvi:.2f}, curr={curr_ndvi:.2f} (drop={ndvi_drop:.2f})")
    evidence.append(f"BSI curr={curr_bsi:.2f}")

    # Check for Cleared status: high Bare Soil Index (BSI)
    if curr_bsi >= cfg.bsi_cleared_threshold:
        detected_state = FieldState.CLEARED
        conf = min(0.98, max(0.60, 0.75 + (curr_bsi - cfg.bsi_cleared_threshold) * 0.8))
        evidence.append(f"Bare soil index {curr_bsi:.2f} >= threshold {cfg.bsi_cleared_threshold:.2f}")

    # Check for Harvested (Residue Present): drop in NDVI
    elif ndvi_drop >= cfg.ndvi_harvest_drop_threshold or curr_ndvi <= 0.35:
        detected_state = FieldState.HARVESTED_RESIDUE_PRESENT
        conf = min(0.96, max(0.60, 0.70 + (ndvi_drop - cfg.ndvi_harvest_drop_threshold) * 0.9))
        evidence.append(f"NDVI drop {ndvi_drop:.2f} >= threshold {cfg.ndvi_harvest_drop_threshold:.2f}")

    # Standing crop: not yet harvested
    else:
        detected_state = FieldState.NOT_HARVESTED
        conf = min(0.95, max(0.65, 0.75 + (curr_ndvi - 0.40) * 0.5))
        evidence.append(f"High standing green canopy NDVI={curr_ndvi:.2f}")

    # 3. Confidence and approval escalation check
    min_approval_conf = cfg.field_monitor_min_confidence_approval
    requires_approval = conf < min_approval_conf
    approval_reason = None
    if requires_approval:
        approval_reason = (
            f"Field {req.field_id} state transition to {detected_state.value} has low confidence "
            f"({conf:.2f} < threshold {min_approval_conf:.2f})"
        )
        evidence.append(approval_reason)

    return FieldObservation(
        field_id=req.field_id,
        timestamp=now,
        detected_state=detected_state,
        confidence=round(conf, 3),
        thermal_anomaly_detected=False,
        source=req.source,
        ndvi_drop=round(ndvi_drop, 3),
        current_bsi=round(curr_bsi, 3),
        requires_approval=requires_approval,
        approval_reason=approval_reason,
        evidence=evidence,
    )


def detect_field_states(
    input_data: FieldMonitorInput,
    settings: Settings | None = None,
) -> FieldMonitorOutput:
    """Processes batch observations for all requested fields in district."""
    observations: list[FieldObservation] = []
    harvested_cnt = 0
    cleared_cnt = 0
    burn_cnt = 0
    approval_cnt = 0

    # Build requests from input_data.fields or default from input_data.field_ids
    requests_to_process = list(input_data.fields)
    if not requests_to_process and input_data.field_ids:
        for f_id in input_data.field_ids:
            # Default harvest scenario for field_ids input
            requests_to_process.append(
                FieldObservationRequest(
                    field_id=f_id,
                    previous_state=FieldState.NOT_HARVESTED,
                    pre_harvest_ndvi=0.72,
                    current_ndvi=0.28,
                    current_bsi=-0.05,
                    source="sentinel2_mock",
                )
            )

    for f_req in requests_to_process:
        res = evaluate_field_observation(f_req, settings=settings)
        observations.append(res)

        if res.requires_approval:
            approval_cnt += 1
        if res.detected_state == FieldState.BURN_DETECTED:
            burn_cnt += 1
        elif (
            res.detected_state == FieldState.HARVESTED_RESIDUE_PRESENT
            and res.previous_state == FieldState.NOT_HARVESTED
        ):
            harvested_cnt += 1
        elif res.detected_state == FieldState.CLEARED and res.previous_state != FieldState.CLEARED:
            cleared_cnt += 1

    return FieldMonitorOutput(
        district=input_data.district,
        observations=observations,
        newly_harvested_count=harvested_cnt,
        cleared_count=cleared_cnt,
        burn_detected_count=burn_cnt,
        approvals_requested_count=approval_cnt,
    )


def build_field_events(
    result: FieldObservation,
    *,
    at: datetime | None = None,
) -> list[EventPayload]:
    """Generates typed domain events for state change or burn detection."""
    events: list[EventPayload] = []
    now = at or datetime.now(IST)

    if result.detected_state == FieldState.BURN_DETECTED:
        events.append(
            BurnDetected(
                field_id=result.field_id,
                detected_at=now,
                source="firms",
                confidence=result.confidence,
            )
        )

    if result.detected_state != result.previous_state:
        events.append(
            FieldStateChanged(
                field_id=result.field_id,
                previous=result.previous_state,
                new=result.detected_state,
                confidence=result.confidence,
                evidence=result.evidence,
            )
        )

    return events
