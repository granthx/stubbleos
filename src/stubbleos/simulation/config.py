"""Scenario configuration and Pydantic validation for the district simulator."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from stubbleos.core.types import LandholdingClass, MachineType


class DistrictSizeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    num_farmers: Annotated[int, Field(ge=5, le=50000, description="Total number of farmers")]
    fields_per_farmer_min: Annotated[int, Field(ge=1, le=10)] = 1
    fields_per_farmer_max: Annotated[int, Field(ge=1, le=10)] = 3
    landholding_distribution: dict[LandholdingClass, float] = Field(
        default_factory=lambda: {
            LandholdingClass.MARGINAL: 0.35,
            LandholdingClass.SMALL: 0.30,
            LandholdingClass.SEMI_MEDIUM: 0.20,
            LandholdingClass.MEDIUM: 0.12,
            LandholdingClass.LARGE: 0.03,
        }
    )

    @model_validator(mode="after")
    def validate_fields_and_distribution(self) -> DistrictSizeConfig:
        if self.fields_per_farmer_min > self.fields_per_farmer_max:
            raise ValueError("fields_per_farmer_min cannot exceed fields_per_farmer_max")
        total_p = sum(self.landholding_distribution.values())
        if abs(total_p - 1.0) > 1e-4:
            raise ValueError(f"landholding_distribution probabilities must sum to 1.0, got {total_p:.4f}")
        return self


class MachineCountsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    happy_seeder: Annotated[int, Field(ge=0)] = 15
    super_seeder: Annotated[int, Field(ge=0)] = 20
    baler: Annotated[int, Field(ge=0)] = 10
    rake: Annotated[int, Field(ge=0)] = 10

    def total(self) -> int:
        return self.happy_seeder + self.super_seeder + self.baler + self.rake

    def count_for(self, machine_type: MachineType) -> int:
        mapping = {
            MachineType.HAPPY_SEEDER: self.happy_seeder,
            MachineType.SUPER_SEEDER: self.super_seeder,
            MachineType.BALER: self.baler,
            MachineType.RAKE: self.rake,
        }
        return mapping[machine_type]


class StochasticParamsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rain_shock_severity: Annotated[float, Field(ge=0.0, le=1.0)] = 0.15
    rain_duration_hours_min: Annotated[float, Field(ge=1.0, le=120.0)] = 24.0
    rain_duration_hours_max: Annotated[float, Field(ge=1.0, le=120.0)] = 48.0
    machine_breakdown_rate_per_day: Annotated[float, Field(ge=0.0, le=1.0)] = 0.04
    mean_repair_hours: Annotated[float, Field(ge=1.0, le=168.0)] = 20.0
    farmer_trust_mean: Annotated[float, Field(ge=0.0, le=1.0)] = 0.60
    farmer_trust_std: Annotated[float, Field(ge=0.0, le=0.5)] = 0.15
    deadline_window_days_min: Annotated[int, Field(ge=3, le=45)] = 10
    deadline_window_days_max: Annotated[int, Field(ge=3, le=45)] = 20

    @model_validator(mode="after")
    def validate_bounds(self) -> StochasticParamsConfig:
        if self.rain_duration_hours_min > self.rain_duration_hours_max:
            raise ValueError("rain_duration_hours_min cannot exceed rain_duration_hours_max")
        if self.deadline_window_days_min > self.deadline_window_days_max:
            raise ValueError("deadline_window_days_min cannot exceed deadline_window_days_max")
        return self


class BuyerSpecConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    num_biomass_plants: Annotated[int, Field(ge=0)] = 2
    num_cbg_plants: Annotated[int, Field(ge=0)] = 2
    num_paper_mills: Annotated[int, Field(ge=0)] = 1
    target_total_demand_tonnes: Annotated[float, Field(ge=0.0)] = 15000.0
    price_inr_per_tonne_min: Annotated[float, Field(ge=500.0, le=5000.0)] = 1500.0
    price_inr_per_tonne_max: Annotated[float, Field(ge=500.0, le=5000.0)] = 2200.0

    @model_validator(mode="after")
    def validate_prices(self) -> BuyerSpecConfig:
        if self.price_inr_per_tonne_min > self.price_inr_per_tonne_max:
            raise ValueError("price_inr_per_tonne_min cannot exceed price_inr_per_tonne_max")
        return self


class ScenarioConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1)
    description: str = ""
    district_name: str = "ludhiana"
    season_start: datetime = datetime(2026, 10, 15, 0, 0, tzinfo=UTC)
    season_length_days: Annotated[int, Field(ge=7, le=120)] = 35
    truck_count: Annotated[int, Field(ge=1)] = 25
    district_size: DistrictSizeConfig = Field(default_factory=lambda: DistrictSizeConfig(num_farmers=150))
    machine_counts: MachineCountsConfig = Field(default_factory=MachineCountsConfig)
    stochastic_parameters: StochasticParamsConfig = Field(default_factory=StochasticParamsConfig)
    buyer_specs: BuyerSpecConfig = Field(default_factory=BuyerSpecConfig)
    calibration_file: str | None = None
    is_synthetic: bool = True

    def config_hash(self) -> str:
        """Deterministic sha256 hash of the configuration JSON."""
        data = self.model_dump_json(exclude={"calibration_file"})
        return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def from_yaml_file(cls, path: str | Path) -> ScenarioConfig:
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Scenario configuration file not found: {file_path}")
        with open(file_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        if not isinstance(raw, dict):
            raise ValueError(f"Scenario YAML must be a mapping, got {type(raw).__name__}")
        return cls.model_validate(raw)

    @classmethod
    def from_yaml_str(cls, yaml_content: str) -> ScenarioConfig:
        raw = yaml.safe_load(yaml_content)
        if not isinstance(raw, dict):
            raise ValueError(f"Scenario YAML must be a mapping, got {type(raw).__name__}")
        return cls.model_validate(raw)
