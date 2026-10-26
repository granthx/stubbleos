"""Synthetic district generator producing calibrated, reproducible farm and market structures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

import numpy as np

from stubbleos.core.ids import SeededUUIDFactory
from stubbleos.core.types import (
    BuyerType,
    FieldState,
    LandholdingClass,
    Language,
    MachineStatus,
    MachineType,
)
from stubbleos.simulation.config import ScenarioConfig
from stubbleos.simulation.model import (
    DistrictState,
    SimulatedBuyer,
    SimulatedFarmer,
    SimulatedField,
    SimulatedMachine,
    SimulatedOperator,
    SimulatedTruck,
)

# Realistic landholding acreage bands (acres) according to Indian agricultural census categories
ACRES_BY_CLASS = {
    LandholdingClass.MARGINAL: (1.0, 2.5),
    LandholdingClass.SMALL: (2.5, 5.0),
    LandholdingClass.SEMI_MEDIUM: (5.0, 10.0),
    LandholdingClass.MEDIUM: (10.0, 25.0),
    LandholdingClass.LARGE: (25.0, 50.0),
}

# Machine specifications (capacity acres/hr, hourly cost in INR)
MACHINE_SPECS = {
    MachineType.HAPPY_SEEDER: {"capacity": (1.0, 1.25), "cost": (1600.0, 2000.0)},
    MachineType.SUPER_SEEDER: {"capacity": (1.2, 1.6), "cost": (1800.0, 2200.0)},
    MachineType.BALER: {"capacity": (1.8, 2.5), "cost": (2200.0, 2800.0)},
    MachineType.RAKE: {"capacity": (3.0, 4.2), "cost": (900.0, 1200.0)},
}

# Average paddy straw residue yield in Punjab: ~2.5 to 2.8 tonnes per acre
RESIDUE_TONNES_PER_ACRE_RANGE = (2.4, 2.8)


def load_calibration_params(file_path: str | None) -> dict[str, Any]:
    """Optional calibration hook loading district-level empirical parameters from a JSON/YAML file."""
    if not file_path:
        return {}
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"Calibration file not found: {p}")
    with open(p, encoding="utf-8") as f:
        return json.load(f)  # type: ignore[no-any-return]


def generate_synthetic_district(config: ScenarioConfig, seed: int) -> DistrictState:
    """Generate a fully synthetic, reproducible district state governed by seed."""
    rng = np.random.default_rng(seed)
    id_factory = SeededUUIDFactory(seed)

    # Optional calibration parameters override defaults if provided
    calib = load_calibration_params(config.calibration_file)

    # District spatial bounds (default: Ludhiana district region, Punjab, India)
    min_lat, max_lat = calib.get("lat_bounds", (30.72, 30.98))
    min_lon, max_lon = calib.get("lon_bounds", (75.65, 75.98))

    classes = list(config.district_size.landholding_distribution.keys())
    probs = [config.district_size.landholding_distribution[c] for c in classes]

    farmers: list[SimulatedFarmer] = []
    fields: list[SimulatedField] = []

    # 1. Generate Farmers and Fields
    for i in range(config.district_size.num_farmers):
        farmer_id = id_factory()
        land_cls = rng.choice(classes, p=probs)
        min_a, max_a = ACRES_BY_CLASS[land_cls]
        total_acres = float(rng.uniform(min_a, max_a))

        # Trust score sampled from clamped normal distribution
        trust = float(
            np.clip(
                rng.normal(
                    config.stochastic_parameters.farmer_trust_mean,
                    config.stochastic_parameters.farmer_trust_std,
                ),
                0.05,
                0.95,
            )
        )

        income_band = (
            "low"
            if land_cls in (LandholdingClass.MARGINAL, LandholdingClass.SMALL)
            else "medium"
            if land_cls == LandholdingClass.SEMI_MEDIUM
            else "high"
        )
        lang = Language.PUNJABI if rng.random() < 0.85 else Language.HINDI

        # Farmer center location
        farmer_lat = float(rng.uniform(min_lat, max_lat))
        farmer_lon = float(rng.uniform(min_lon, max_lon))

        # Divide farmer's total area across 1 to N fields
        n_fields = int(
            rng.integers(
                config.district_size.fields_per_farmer_min,
                config.district_size.fields_per_farmer_max + 1,
            )
        )
        # Random area splits ensuring each field has meaningful positive area
        if n_fields == 1:
            raw_areas = np.array([total_acres])
        else:
            splits = rng.dirichlet(np.full(n_fields, 4.0))
            raw_areas = splits * total_acres
            min_field_a = min(0.2, total_acres / (2.0 * n_fields))
            raw_areas = np.maximum(raw_areas, min_field_a)
            raw_areas = (raw_areas / np.sum(raw_areas)) * total_acres
        farmer_field_ids: list[UUID] = []

        # Harvest day spread across first 60% of season
        harvest_window_days = max(5, int(config.season_length_days * 0.6))
        base_harvest_day = float(rng.uniform(1.0, float(harvest_window_days)))

        for f_idx in range(n_fields):
            f_id = id_factory()
            farmer_field_ids.append(f_id)
            field_area = max(0.05, float(raw_areas[f_idx]))
            residue_factor = float(rng.uniform(*RESIDUE_TONNES_PER_ACRE_RANGE))
            residue_tonnes = max(0.1, field_area * residue_factor)

            # Harvest day with small intra-farm variance (within 1-2 days)
            f_harvest_day = float(
                np.clip(base_harvest_day + rng.uniform(-1.0, 1.0), 1.0, config.season_length_days - 5)
            )
            deadline_window = int(
                rng.integers(
                    config.stochastic_parameters.deadline_window_days_min,
                    config.stochastic_parameters.deadline_window_days_max + 1,
                )
            )
            sowing_deadline = f_harvest_day + float(deadline_window)

            # Field centroid offset slightly from farmer centroid
            f_lat = farmer_lat + float(rng.uniform(-0.015, 0.015))
            f_lon = farmer_lon + float(rng.uniform(-0.015, 0.015))

            # Approximate square polygon
            deg_offset = math_deg_offset_for_acres(field_area)
            polygon = [
                (f_lat - deg_offset, f_lon - deg_offset),
                (f_lat - deg_offset, f_lon + deg_offset),
                (f_lat + deg_offset, f_lon + deg_offset),
                (f_lat + deg_offset, f_lon - deg_offset),
            ]

            fields.append(
                SimulatedField(
                    field_id=f_id,
                    farmer_id=farmer_id,
                    area_acres=round(field_area, 2),
                    residue_tonnes_est=round(residue_tonnes, 2),
                    harvest_day=round(f_harvest_day, 2),
                    sowing_deadline_day=round(sowing_deadline, 2),
                    state=FieldState.NOT_HARVESTED,
                    center_lat=round(f_lat, 5),
                    center_lon=round(f_lon, 5),
                    polygon_coords=polygon,
                    is_synthetic=True,
                )
            )

        farmers.append(
            SimulatedFarmer(
                farmer_id=farmer_id,
                pseudonym=f"farmer_syn_{seed % 10000}_{i:04d}",
                landholding_class=land_cls,
                total_area_acres=round(total_acres, 2),
                trust_score=round(trust, 3),
                income_band=income_band,
                preferred_language=lang,
                field_ids=farmer_field_ids,
                is_synthetic=True,
            )
        )

    # 2. Generate Machines
    machines: list[SimulatedMachine] = []
    machine_counts = config.machine_counts

    for m_type in [
        MachineType.HAPPY_SEEDER,
        MachineType.SUPER_SEEDER,
        MachineType.BALER,
        MachineType.RAKE,
    ]:
        count = machine_counts.count_for(m_type)
        spec = MACHINE_SPECS[m_type]
        for _ in range(count):
            m_id = id_factory()
            cap = float(rng.uniform(*spec["capacity"]))
            cost = float(rng.uniform(*spec["cost"]))
            h_lat = float(rng.uniform(min_lat, max_lat))
            h_lon = float(rng.uniform(min_lon, max_lon))
            machines.append(
                SimulatedMachine(
                    machine_id=m_id,
                    machine_type=m_type,
                    capacity_acres_per_hour=round(cap, 2),
                    hourly_cost_inr=round(cost, 2),
                    status=MachineStatus.AVAILABLE,
                    current_lat=round(h_lat, 5),
                    current_lon=round(h_lon, 5),
                    home_lat=round(h_lat, 5),
                    home_lon=round(h_lon, 5),
                    is_synthetic=True,
                )
            )

    # 3. Generate Operators (one operator per machine, plus 10% reserve)
    operators: list[SimulatedOperator] = []
    total_machines = len(machines)
    num_operators = int(total_machines * 1.1)
    for op_idx in range(num_operators):
        op_id = id_factory()
        # Certify for 1-2 machine types
        cert_types = list(rng.choice(list(MachineType), size=int(rng.integers(1, 3)), replace=False))
        operators.append(
            SimulatedOperator(
                operator_id=op_id,
                pseudonym=f"operator_syn_{seed % 10000}_{op_idx:03d}",
                certified_machine_types=cert_types,
                is_active=True,
                is_synthetic=True,
            )
        )

    # 4. Generate Buyers
    buyers: list[SimulatedBuyer] = []
    buyer_plan = [
        (BuyerType.BIOMASS_PLANT, config.buyer_specs.num_biomass_plants),
        (BuyerType.CBG_PLANT, config.buyer_specs.num_cbg_plants),
        (BuyerType.PAPER_MILL, config.buyer_specs.num_paper_mills),
    ]
    total_buyers = sum(count for _, count in buyer_plan)
    per_buyer_demand = (
        config.buyer_specs.target_total_demand_tonnes / max(1, total_buyers) if total_buyers > 0 else 0.0
    )

    buyer_idx = 0
    for b_type, count in buyer_plan:
        for _ in range(count):
            b_id = id_factory()
            demand = float(rng.uniform(per_buyer_demand * 0.8, per_buyer_demand * 1.2))
            price = float(
                rng.uniform(
                    config.buyer_specs.price_inr_per_tonne_min,
                    config.buyer_specs.price_inr_per_tonne_max,
                )
            )
            # Positioned near peripheral industrial edges
            edge = rng.choice(["N", "S", "E", "W"])
            if edge == "N":
                b_lat, b_lon = max_lat + 0.02, float(rng.uniform(min_lon, max_lon))
            elif edge == "S":
                b_lat, b_lon = min_lat - 0.02, float(rng.uniform(min_lon, max_lon))
            elif edge == "E":
                b_lat, b_lon = float(rng.uniform(min_lat, max_lat)), max_lon + 0.02
            else:
                b_lat, b_lon = float(rng.uniform(min_lat, max_lat)), min_lon - 0.02

            buyers.append(
                SimulatedBuyer(
                    buyer_id=b_id,
                    org_name=f"Buyer_{b_type.value}_{buyer_idx:02d}_syn",
                    buyer_type=b_type,
                    lat=round(b_lat, 5),
                    lon=round(b_lon, 5),
                    tonnes_required=round(demand, 1),
                    tonnes_filled=0.0,
                    price_inr_per_tonne=round(price, 1),
                    max_moisture_pct=16.0 if b_type != BuyerType.CBG_PLANT else 22.0,
                    is_synthetic=True,
                )
            )
            buyer_idx += 1

    # 5. Generate Trucks
    trucks: list[SimulatedTruck] = []
    for _ in range(config.truck_count):
        t_id = id_factory()
        cap = float(rng.uniform(9.0, 12.0))
        cost = float(rng.uniform(40.0, 50.0))
        trucks.append(
            SimulatedTruck(
                truck_id=t_id,
                capacity_tonnes=round(cap, 1),
                cost_per_km_inr=round(cost, 1),
                is_available=True,
                is_synthetic=True,
            )
        )

    return DistrictState(
        district_name=config.district_name,
        farmers=farmers,
        fields=fields,
        machines=machines,
        operators=operators,
        buyers=buyers,
        trucks=trucks,
        is_synthetic=True,
    )


def math_deg_offset_for_acres(acres: float) -> float:
    """Approximate half-side degree length for a square field of given acreage at Punjab latitude (~31° N)."""
    # 1 acre = 4046.86 m^2. Side = sqrt(acres * 4047)
    side_meters = np.sqrt(acres * 4047.0)
    # At latitude 31, 1 degree latitude ~ 110,800 m.
    half_side_deg = (side_meters / 2.0) / 110800.0
    return float(half_side_deg)
