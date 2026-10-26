"""Unit tests for simulation configuration parsing and Pydantic validation."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from stubbleos.core.types import LandholdingClass
from stubbleos.simulation.config import (
    BuyerSpecConfig,
    DistrictSizeConfig,
    MachineCountsConfig,
    ScenarioConfig,
    StochasticParamsConfig,
)


def test_scenario_config_valid_defaults() -> None:
    config = ScenarioConfig(name="test-scenario")
    assert config.name == "test-scenario"
    assert config.season_length_days == 35
    assert config.is_synthetic is True
    assert len(config.config_hash()) == 16


def test_district_size_invalid_farmer_count() -> None:
    with pytest.raises(ValidationError, match="greater than or equal to 5"):
        DistrictSizeConfig(num_farmers=2)


def test_district_size_min_exceeds_max() -> None:
    with pytest.raises(ValidationError, match="fields_per_farmer_min cannot exceed fields_per_farmer_max"):
        DistrictSizeConfig(num_farmers=10, fields_per_farmer_min=5, fields_per_farmer_max=3)


def test_district_size_probabilities_must_sum_to_one() -> None:
    with pytest.raises(ValidationError, match=r"probabilities must sum to 1\.0"):
        DistrictSizeConfig(
            num_farmers=10,
            landholding_distribution={
                LandholdingClass.MARGINAL: 0.5,
                LandholdingClass.SMALL: 0.2,
                LandholdingClass.SEMI_MEDIUM: 0.1,
                LandholdingClass.MEDIUM: 0.1,
                LandholdingClass.LARGE: 0.05,  # sums to 0.95
            },
        )


def test_machine_counts_total() -> None:
    counts = MachineCountsConfig(happy_seeder=10, super_seeder=15, baler=5, rake=5)
    assert counts.total() == 35


def test_stochastic_params_validation_errors() -> None:
    with pytest.raises(
        ValidationError, match="rain_duration_hours_min cannot exceed rain_duration_hours_max"
    ):
        StochasticParamsConfig(rain_duration_hours_min=50.0, rain_duration_hours_max=20.0)

    with pytest.raises(
        ValidationError, match="deadline_window_days_min cannot exceed deadline_window_days_max"
    ):
        StochasticParamsConfig(deadline_window_days_min=25, deadline_window_days_max=10)


def test_buyer_specs_validation_errors() -> None:
    with pytest.raises(
        ValidationError, match="price_inr_per_tonne_min cannot exceed price_inr_per_tonne_max"
    ):
        BuyerSpecConfig(price_inr_per_tonne_min=3000.0, price_inr_per_tonne_max=2000.0)


@pytest.mark.parametrize(
    "scenario_name",
    [
        "baseline-district",
        "machine-scarce",
        "rain-shock",
        "low-trust",
    ],
)
def test_all_provided_scenarios_load_and_validate(scenario_name: str) -> None:
    yaml_path = Path("scenarios") / f"{scenario_name}.yaml"
    assert yaml_path.exists(), f"Scenario file {yaml_path} does not exist"
    config = ScenarioConfig.from_yaml_file(yaml_path)
    assert config.name == scenario_name
    assert config.is_synthetic is True
    assert config.district_size.num_farmers > 0
    assert config.machine_counts.total() > 0
