"""Unit and simulation accuracy tests for Field Monitor agent."""

from __future__ import annotations

import uuid

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from stubbleos.agents.field_monitor.graph import build_field_monitor_graph
from stubbleos.agents.field_monitor.logic import (
    build_field_events,
    evaluate_field_observation,
)
from stubbleos.agents.field_monitor.schemas import (
    FieldMonitorInput,
    FieldMonitorState,
    FieldObservationRequest,
)
from stubbleos.core.config import Settings
from stubbleos.core.types import FieldState
from stubbleos.data.models import Approval, Base
from stubbleos.data.repositories import ApprovalRepository
from stubbleos.simulation.sensor import DistrictSensorModel, SensorConfig

TABLES = [Approval.__table__]


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://").execution_options(schema_translate_map={"core": None, "pii": None})
    Base.metadata.create_all(engine, tables=TABLES)
    sm = sessionmaker(engine, expire_on_commit=False)
    with sm() as s:
        yield s
    engine.dispose()


@pytest.fixture
def approval_repo(session: Session) -> ApprovalRepository:
    return ApprovalRepository(session)


def test_field_monitor_all_four_states() -> None:
    """Verifies that Field Monitor correctly classifies all four domain states."""
    f_id = uuid.uuid4()

    # 1. NOT_HARVESTED: high NDVI, negative BSI, no fires
    req_not_harvested = FieldObservationRequest(
        field_id=f_id,
        pre_harvest_ndvi=0.72,
        current_ndvi=0.70,
        current_bsi=-0.25,
        has_firms_hotspot=False,
    )
    res_not_harvested = evaluate_field_observation(req_not_harvested)
    assert res_not_harvested.detected_state == FieldState.NOT_HARVESTED
    assert res_not_harvested.confidence >= 0.75
    assert res_not_harvested.requires_approval is False

    # 2. HARVESTED_RESIDUE_PRESENT: significant drop in NDVI (>0.25), low BSI
    req_harvested = FieldObservationRequest(
        field_id=f_id,
        pre_harvest_ndvi=0.72,
        current_ndvi=0.30,  # drop = 0.42
        current_bsi=-0.05,
        has_firms_hotspot=False,
    )
    res_harvested = evaluate_field_observation(req_harvested)
    assert res_harvested.detected_state == FieldState.HARVESTED_RESIDUE_PRESENT
    assert res_harvested.confidence >= 0.80

    # 3. CLEARED: high Bare Soil Index (BSI >= 0.15)
    req_cleared = FieldObservationRequest(
        field_id=f_id,
        pre_harvest_ndvi=0.72,
        current_ndvi=0.22,
        current_bsi=0.28,  # > 0.15 bare soil
        has_firms_hotspot=False,
    )
    res_cleared = evaluate_field_observation(req_cleared)
    assert res_cleared.detected_state == FieldState.CLEARED
    assert res_cleared.confidence >= 0.80

    # 4. BURN_DETECTED: active FIRMS thermal hotspot
    req_burn = FieldObservationRequest(
        field_id=f_id,
        pre_harvest_ndvi=0.72,
        current_ndvi=0.15,
        current_bsi=0.20,
        has_firms_hotspot=True,
        firms_confidence_pct=92.0,
    )
    res_burn = evaluate_field_observation(req_burn)
    assert res_burn.detected_state == FieldState.BURN_DETECTED
    assert res_burn.confidence >= 0.90
    assert res_burn.has_thermal_anomaly is True


def test_field_monitor_low_confidence_routes_to_approval(approval_repo: ApprovalRepository) -> None:
    """Verifies that an observation with confidence below threshold escalates to the approval queue."""
    custom_settings = Settings(
        field_monitor_min_confidence_approval=0.85,  # Strict threshold
        ndvi_harvest_drop_threshold=0.25,
    )

    f_id = uuid.uuid4()
    # Marginal observation: NDVI drop is just on the boundary (drop 0.26)
    req = FieldObservationRequest(
        field_id=f_id,
        pre_harvest_ndvi=0.60,
        current_ndvi=0.34,  # drop = 0.26
        current_bsi=-0.15,
        has_firms_hotspot=False,
    )
    res = evaluate_field_observation(req, settings=custom_settings)

    # Should flag approval required
    assert res.requires_approval is True
    assert "low confidence" in (res.approval_reason or "").lower()

    # Test LangGraph escalation node creates Approval record
    inp = FieldMonitorInput(district="Sangrur", fields=[req])
    state = FieldMonitorState(input=inp)
    graph = build_field_monitor_graph(approval_repo=approval_repo, settings=custom_settings)
    result_state = graph.invoke(state, config={"configurable": {"thread_id": "fm_low_conf"}})

    assert result_state["status"] == "completed"
    assert len(result_state["created_approval_ids"]) == 1

    appr = approval_repo.get_by_id(result_state["created_approval_ids"][0])
    assert appr is not None
    assert appr.kind == "field_state_change"
    assert appr.subject_id == f_id


@pytest.mark.asyncio
async def test_field_monitor_event_emission() -> None:
    """Verifies that FieldStateChanged and BurnDetected events are emitted."""
    f_id = uuid.uuid4()

    # Burn detection emits both BurnDetected and FieldStateChanged
    req_burn = FieldObservationRequest(
        field_id=f_id,
        previous_state=FieldState.HARVESTED_RESIDUE_PRESENT,
        has_firms_hotspot=True,
        firms_confidence_pct=88.0,
    )
    res_burn = evaluate_field_observation(req_burn)
    events = build_field_events(res_burn)

    types = {e.event_type for e in events}
    assert "field.burn_detected" in types
    assert "field.state_changed" in types

    # Unchanged state emits no events
    req_same = FieldObservationRequest(
        field_id=f_id,
        previous_state=FieldState.NOT_HARVESTED,
        pre_harvest_ndvi=0.75,
        current_ndvi=0.73,
    )
    res_same = evaluate_field_observation(req_same)
    events_same = build_field_events(res_same)
    assert len(events_same) == 0


def test_field_monitor_accuracy_on_synthetic_ground_truth() -> None:
    """Simulates 100 fields with controllable sensor noise and verifies high detection accuracy."""
    rng = np.random.default_rng(2026)
    sensor_model = DistrictSensorModel(
        SensorConfig(
            cloud_cover_prob=0.05,
            thermal_false_positive_prob=0.01,
            thermal_false_negative_prob=0.03,
            ndvi_noise_std=0.02,
            bsi_noise_std=0.02,
        )
    )

    states_pool = [
        FieldState.NOT_HARVESTED,
        FieldState.HARVESTED_RESIDUE_PRESENT,
        FieldState.CLEARED,
        FieldState.BURN_DETECTED,
    ]

    ground_truth: list[FieldState] = []
    detected: list[FieldState] = []

    for _ in range(100):
        f_id = uuid.uuid4()
        true_state = rng.choice(states_pool)
        ground_truth.append(true_state)

        # Generate noisy synthetic observation
        obs = sensor_model.generate_observation(f_id, true_state, rng)

        # If not cloud-obscured, classify
        if not obs.is_cloud_obscured:
            req = sensor_model.to_observation_request(obs, previous_state=FieldState.NOT_HARVESTED)
            res = evaluate_field_observation(req)
            detected.append(res.detected_state)
        else:
            # Fallback to previous state on heavy cloud cover
            detected.append(FieldState.NOT_HARVESTED)

    metrics = DistrictSensorModel.calculate_accuracy_metrics(ground_truth, detected)

    # Verify sensor precision and recall vs simulated ground truth
    assert metrics["overall_accuracy"] >= 0.85
    assert metrics["burn_precision"] >= 0.85
    assert metrics["burn_recall"] >= 0.85
    assert metrics["burn_f1"] >= 0.85
