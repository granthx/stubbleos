"""Unit tests for simulation metrics computation and aggregation with hand-computed tiny cases."""

from uuid import uuid4

from stubbleos.core.types import (
    BuyerType,
    FieldState,
    LandholdingClass,
    Language,
    MachineStatus,
    MachineType,
)
from stubbleos.simulation.metrics import (
    compute_confidence_intervals,
    compute_run_metrics,
)
from stubbleos.simulation.model import (
    DistrictState,
    SimulatedBuyer,
    SimulatedFarmer,
    SimulatedField,
    SimulatedMachine,
    SimulatedTruck,
)
from stubbleos.simulation.strategy import BaselineAStrategy


def test_hand_computed_tiny_district_metrics() -> None:
    # 4 farmers: 2 smallholders (marginal, small), 2 largeholders (medium, large)
    farmer_a = SimulatedFarmer(
        farmer_id=uuid4(),
        pseudonym="farmer_a",
        landholding_class=LandholdingClass.MARGINAL,
        total_area_acres=2.0,
        trust_score=0.8,
        income_band="low",
        preferred_language=Language.PUNJABI,
        field_ids=[],
        net_income_inr=5000.0,
    )
    farmer_b = SimulatedFarmer(
        farmer_id=uuid4(),
        pseudonym="farmer_b",
        landholding_class=LandholdingClass.SMALL,
        total_area_acres=3.0,
        trust_score=0.6,
        income_band="low",
        preferred_language=Language.PUNJABI,
        field_ids=[],
        net_income_inr=3000.0,
    )
    farmer_c = SimulatedFarmer(
        farmer_id=uuid4(),
        pseudonym="farmer_c",
        landholding_class=LandholdingClass.MEDIUM,
        total_area_acres=5.0,
        trust_score=0.5,
        income_band="medium",
        preferred_language=Language.HINDI,
        field_ids=[],
        net_income_inr=-7500.0,
    )
    farmer_d = SimulatedFarmer(
        farmer_id=uuid4(),
        pseudonym="farmer_d",
        landholding_class=LandholdingClass.LARGE,
        total_area_acres=10.0,
        trust_score=0.4,
        income_band="high",
        preferred_language=Language.PUNJABI,
        field_ids=[],
        net_income_inr=0.0,
    )

    # 4 fields matching the hand-computed scenario
    field_1 = SimulatedField(
        field_id=uuid4(),
        farmer_id=farmer_a.farmer_id,
        area_acres=2.0,
        residue_tonnes_est=5.0,
        harvest_day=5.0,
        sowing_deadline_day=15.0,
        state=FieldState.CLEARED,
        cleared_at_day=12.0,  # Cleared BEFORE deadline
        center_lat=30.8,
        center_lon=75.8,
        polygon_coords=[],
    )
    field_2 = SimulatedField(
        field_id=uuid4(),
        farmer_id=farmer_b.farmer_id,
        area_acres=3.0,
        residue_tonnes_est=7.5,
        harvest_day=5.0,
        sowing_deadline_day=16.0,
        state=FieldState.CLEARED,
        cleared_at_day=18.0,  # Cleared AFTER deadline
        center_lat=30.81,
        center_lon=75.81,
        polygon_coords=[],
    )
    field_3 = SimulatedField(
        field_id=uuid4(),
        farmer_id=farmer_c.farmer_id,
        area_acres=5.0,
        residue_tonnes_est=12.5,
        harvest_day=6.0,
        sowing_deadline_day=14.0,
        state=FieldState.BURN_DETECTED,
        burned_at_day=14.0,  # Burned!
        center_lat=30.82,
        center_lon=75.82,
        polygon_coords=[],
    )
    field_4 = SimulatedField(
        field_id=uuid4(),
        farmer_id=farmer_d.farmer_id,
        area_acres=10.0,
        residue_tonnes_est=25.0,
        harvest_day=7.0,
        sowing_deadline_day=20.0,
        state=FieldState.HARVESTED_RESIDUE_PRESENT,
        center_lat=30.83,
        center_lon=75.83,
        polygon_coords=[],
    )

    # 2 machines
    machine_1 = SimulatedMachine(
        machine_id=uuid4(),
        machine_type=MachineType.HAPPY_SEEDER,
        capacity_acres_per_hour=1.0,
        hourly_cost_inr=1800.0,
        status=MachineStatus.AVAILABLE,
        current_lat=30.8,
        current_lon=75.8,
        home_lat=30.8,
        home_lon=75.8,
        operating_hours=20.0,
        idle_hours=80.0,
    )
    machine_2 = SimulatedMachine(
        machine_id=uuid4(),
        machine_type=MachineType.BALER,
        capacity_acres_per_hour=2.0,
        hourly_cost_inr=2400.0,
        status=MachineStatus.AVAILABLE,
        current_lat=30.8,
        current_lon=75.8,
        home_lat=30.8,
        home_lon=75.8,
        operating_hours=30.0,
        idle_hours=70.0,
    )

    # 1 buyer and 1 truck
    buyer = SimulatedBuyer(
        buyer_id=uuid4(),
        org_name="Buyer_Bio_syn",
        buyer_type=BuyerType.BIOMASS_PLANT,
        lat=30.9,
        lon=75.9,
        tonnes_required=100.0,
        tonnes_filled=10.0,
        price_inr_per_tonne=2000.0,
        max_moisture_pct=16.0,
    )
    truck = SimulatedTruck(
        truck_id=uuid4(),
        capacity_tonnes=10.0,
        cost_per_km_inr=45.0,
        total_km_travelled=100.0,
        total_tonnes_hauled=10.0,
    )

    state = DistrictState(
        district_name="tiny-test",
        farmers=[farmer_a, farmer_b, farmer_c, farmer_d],
        fields=[field_1, field_2, field_3, field_4],
        machines=[machine_1, machine_2],
        operators=[],
        buyers=[buyer],
        trucks=[truck],
    )

    strat = BaselineAStrategy()
    metrics = compute_run_metrics(
        state=state,
        strategy=strat,
        scenario_name="tiny-test",
        seed=1,
        config_hash="abc12345",
        season_length_days=10,  # 10 days * 24h = 240 hours per machine -> 480 total machine capacity hours
        baseline_a_avg_income=100.0,
    )

    # 1. % fields cleared before deadline: 1 out of 4 = 25.0%
    assert metrics.pct_fields_cleared_before_deadline == 25.0

    # 2. Total acres = 2 + 3 + 5 + 10 = 20.0
    assert metrics.total_acres == 20.0

    # 3. Burn events per 1000 acres: 1 event / 20.0 acres * 1000 = 50.0
    assert metrics.total_burn_events == 1
    assert metrics.burn_events_per_1000_acres == 50.0

    # 4. Machine utilization: (20 + 30) / (2 * 240) = 50 / 480 = 10.42%
    assert metrics.machine_utilization_pct == 10.42

    # 5. Average machine idle hours: (80 + 70) / 2 = 75.0
    assert metrics.average_machine_idle_hours == 75.0

    # 6. Straw delivered & fill rate: 10 tonnes delivered / 100 required = 10.0%
    assert metrics.straw_tonnage_delivered == 10.0
    assert metrics.buyer_order_fill_rate_pct == 10.0

    # 7. Average farmer income: (5000 + 3000 - 7500 + 0) / 4 = 500 / 4 = 125.0 INR
    assert metrics.avg_farmer_net_income_inr == 125.0
    assert metrics.farmer_net_income_delta_vs_baseline_a == 25.0  # 125.0 - 100.0

    # 8. Logistics cost and CO2 per ton: 100 km * 45 INR/km / 10 tons = 450.0 INR/ton
    assert metrics.logistics_cost_per_ton_inr == 450.0
    # CO2: 100 km * 1.42 kg/km / 10 tons = 14.2 kg CO2/ton
    assert metrics.logistics_co2_kg_per_ton == 14.2

    # 9. Fairness gap:
    # Smallholders: farmer_a (cleared before deadline), farmer_b (cleared late) -> 1/2 = 50.0%
    # Largeholders: farmer_c (burned), farmer_d (uncleared) -> 0/2 = 0.0%
    # Gap = Large (0.0) - Small (50.0) = -50.0%
    assert metrics.smallholder_clearance_pct == 50.0
    assert metrics.largeholder_clearance_pct == 0.0
    assert metrics.fairness_gap_pct == -50.0


def test_confidence_intervals_constant_and_normal() -> None:
    # Constant array
    ci_t, ci_boot = compute_confidence_intervals([15.0, 15.0, 15.0, 15.0])
    assert ci_t == (15.0, 15.0)
    assert ci_boot == (15.0, 15.0)

    # Varying array: mean = 30.0
    vals = [10.0, 20.0, 30.0, 40.0, 50.0]
    ci_t, ci_boot = compute_confidence_intervals(vals)
    assert ci_t[0] < 30.0 < ci_t[1]
    assert ci_boot[0] < 30.0 < ci_boot[1]
