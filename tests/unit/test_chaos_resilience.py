"""Unit tests for chaos engineering and resilience assertions."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import create_engine

from stubbleos.evals.chaos import (
    run_all_chaos_tests,
    run_audit_tampering_chaos,
    run_double_booking_conflict_chaos,
    run_machine_breakdown_chaos,
    run_quiet_hours_chaos,
    run_spatial_privacy_export_chaos,
)
from stubbleos.evals.privacy import (
    ExportFieldRecord,
    SpatialExportPolicyViolation,
    sanitize_for_external_export,
    validate_export_payload,
)


@pytest.fixture
def test_engine():
    return create_engine(
        "sqlite:///:memory:",
        execution_options={"schema_translate_map": {"core": None, "pii": None}},
    )


def test_machine_breakdown_chaos():
    res = run_machine_breakdown_chaos()
    assert res.passed is True
    assert "machine_breakdown_50pct" in res.name


def test_quiet_hours_chaos():
    res = run_quiet_hours_chaos()
    assert res.passed is True
    assert "quiet_hours_breach_protection" in res.name


def test_audit_tampering_chaos(test_engine):
    res = run_audit_tampering_chaos(test_engine)
    assert res.passed is True
    assert "audit_tamper_detection" in res.name


def test_double_booking_conflict_chaos():
    res = run_double_booking_conflict_chaos()
    assert res.passed is True
    assert "conflict_resolution_and_fairness" in res.name


def test_spatial_privacy_export_chaos():
    res = run_spatial_privacy_export_chaos()
    assert res.passed is True
    assert "spatial_privacy_export_policy" in res.name


def test_run_all_chaos_tests(test_engine):
    results = run_all_chaos_tests(test_engine)
    assert len(results) == 5
    for r in results:
        assert r.passed is True, f"Chaos test {r.name} failed: {r.details}"


def test_spatial_export_policy_violations():
    # Sensitive boundary_wkt key
    with pytest.raises(SpatialExportPolicyViolation):
        validate_export_payload({"district": "ludhiana", "boundary_wkt": "POLYGON(...)"})

    # Sensitive farmer phone
    with pytest.raises(SpatialExportPolicyViolation):
        validate_export_payload({"district": "ludhiana", "records": [{"phone_number": "+919876543210"}]})


def test_sanitize_for_external_export_k_anonymity():
    # 2 fields in village A (below k=3), 4 fields in village B (>= k=3)
    records = [
        ExportFieldRecord(
            field_id=uuid4(),
            farmer_id=uuid4(),
            village_name="small_hamlet",
            district_name="ludhiana",
            area_acres=3.0,
            center_lat=30.80,
            center_lon=75.80,
            harvest_day=1.0,
            sowing_deadline_day=15.0,
            cleared_at_day=10.0,
            burned=False,
        )
        for _ in range(2)
    ] + [
        ExportFieldRecord(
            field_id=uuid4(),
            farmer_id=uuid4(),
            village_name="large_village",
            district_name="ludhiana",
            area_acres=5.0,
            center_lat=30.85,
            center_lon=75.85,
            harvest_day=1.0,
            sowing_deadline_day=15.0,
            cleared_at_day=12.0,
            burned=False,
        )
        for _ in range(4)
    ]

    summaries = sanitize_for_external_export(records, min_k_anonymity=3)
    assert len(summaries) == 2

    # Check village-level summary
    village_b = next(s for s in summaries if s.village_name == "large_village")
    assert village_b.total_fields == 4
    assert village_b.spatial_precision == "village_centroid"

    # Check district fallback residual
    residual = next(s for s in summaries if "residual" in s.village_name)
    assert residual.total_fields == 2
    assert residual.spatial_precision == "district_centroid_fallback"
