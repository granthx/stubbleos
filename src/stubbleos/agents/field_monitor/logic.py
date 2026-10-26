"""Logic and mock detection for Field Monitor agent."""

from __future__ import annotations

from datetime import datetime

from stubbleos.agents.field_monitor.schemas import (
    FieldMonitorInput,
    FieldMonitorOutput,
    FieldObservation,
)
from stubbleos.core.clock import IST
from stubbleos.core.types import FieldState


def detect_field_states(input_data: FieldMonitorInput) -> FieldMonitorOutput:
    """Mock satellite sensing logic for field harvest and burn detection."""
    observations: list[FieldObservation] = []
    harvested_cnt = 0
    burn_cnt = 0

    now = datetime.now(IST)
    for f_id in input_data.field_ids:
        # Default mock: mark as harvested residue present
        obs = FieldObservation(
            field_id=f_id,
            timestamp=now,
            detected_state=FieldState.HARVESTED_RESIDUE_PRESENT,
            confidence=0.92,
            thermal_anomaly_detected=False,
            source="sentinel2_mock",
        )
        observations.append(obs)
        harvested_cnt += 1

    return FieldMonitorOutput(
        observations=observations,
        newly_harvested_count=harvested_cnt,
        burn_detected_count=burn_cnt,
    )
