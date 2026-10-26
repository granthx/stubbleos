"""Unit tests for synthetic district generation and reproducibility."""

import json
from pathlib import Path

from stubbleos.simulation.config import ScenarioConfig
from stubbleos.simulation.generator import generate_synthetic_district


def test_generator_determinism() -> None:
    config = ScenarioConfig(name="test-sim")
    seed = 42

    district1 = generate_synthetic_district(config, seed)
    district2 = generate_synthetic_district(config, seed)

    assert len(district1.farmers) == len(district2.farmers)
    assert len(district1.fields) == len(district2.fields)
    assert len(district1.machines) == len(district2.machines)
    assert len(district1.buyers) == len(district2.buyers)
    assert len(district1.trucks) == len(district2.trucks)

    for f1, f2 in zip(district1.farmers, district2.farmers, strict=True):
        assert f1.farmer_id == f2.farmer_id
        assert f1.total_area_acres == f2.total_area_acres
        assert f1.trust_score == f2.trust_score

    for fld1, fld2 in zip(district1.fields, district2.fields, strict=True):
        assert fld1.field_id == fld2.field_id
        assert fld1.area_acres == fld2.area_acres
        assert fld1.harvest_day == fld2.harvest_day
        assert fld1.sowing_deadline_day == fld2.sowing_deadline_day


def test_generator_labels_everything_synthetic() -> None:
    config = ScenarioConfig(name="test-sim")
    district = generate_synthetic_district(config, seed=999)

    assert district.is_synthetic is True
    assert all(f.is_synthetic for f in district.farmers)
    assert all(f.is_synthetic for f in district.fields)
    assert all(m.is_synthetic for m in district.machines)
    assert all(op.is_synthetic for op in district.operators)
    assert all(b.is_synthetic for b in district.buyers)
    assert all(t.is_synthetic for t in district.trucks)


def test_generator_calibration_file_hook(tmp_path: object) -> None:
    calib_data = {
        "lat_bounds": [31.0, 31.5],
        "lon_bounds": [76.0, 76.5],
    }
    calib_file = Path(str(tmp_path)) / "calibration.json"
    calib_file.write_text(json.dumps(calib_data), encoding="utf-8")

    config = ScenarioConfig(name="calibrated-test", calibration_file=str(calib_file))
    district = generate_synthetic_district(config, seed=123)

    for f in district.fields:
        assert 30.98 <= f.center_lat <= 31.52
        assert 75.98 <= f.center_lon <= 76.52
