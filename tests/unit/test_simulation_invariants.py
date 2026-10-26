"""Invariants and conservation tests using unit assertions and Hypothesis property tests."""

import math

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from stubbleos.core.types import FieldState
from stubbleos.simulation.config import DistrictSizeConfig, ScenarioConfig
from stubbleos.simulation.simulator import DistrictSimulator
from stubbleos.simulation.strategy import BaselineAStrategy, BaselineBStrategy


def test_conservation_and_physical_invariants() -> None:
    config = ScenarioConfig(name="test-invariants", season_length_days=25)
    strat = BaselineBStrategy()
    sim = DistrictSimulator(config=config, strategy=strat, seed=12345)
    state = sim.run()

    total_season_hours = config.season_length_days * 24.0

    # 1. Total acres conservation
    sum_individual_acres = sum(f.area_acres for f in state.fields)
    assert math.isclose(state.total_acres, sum_individual_acres, rel_tol=1e-5)

    # 2. Partitioning of field states (no overlaps, complete sum)
    cleared_a = sum(f.area_acres for f in state.fields if f.state == FieldState.CLEARED)
    burned_a = sum(f.area_acres for f in state.fields if f.state == FieldState.BURN_DETECTED)
    unharvested_a = sum(f.area_acres for f in state.fields if f.state == FieldState.NOT_HARVESTED)
    uncleared_a = sum(f.area_acres for f in state.fields if f.state == FieldState.HARVESTED_RESIDUE_PRESENT)

    partition_sum = cleared_a + burned_a + unharvested_a + uncleared_a
    assert math.isclose(partition_sum, state.total_acres, rel_tol=1e-5)

    # 3. No field is both cleared and burned
    for field in state.fields:
        assert not (field.is_cleared and field.is_burned), (
            f"Field {field.field_id} is both cleared and burned!"
        )
        assert field.area_acres > 0.0
        assert field.residue_tonnes_est > 0.0

    # 4. Conservation of machine operating hours
    for m in state.machines:
        total_m_hours = m.operating_hours + m.transit_hours + m.breakdown_hours + m.idle_hours
        assert math.isclose(total_m_hours, total_season_hours, abs_tol=0.1)
        assert m.operating_hours >= 0.0
        assert m.idle_hours >= 0.0
        assert m.breakdown_hours >= 0.0
        assert m.transit_hours >= 0.0


@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(
    seed=st.integers(min_value=1, max_value=99999),
    num_farmers=st.integers(min_value=10, max_value=30),
    season_days=st.integers(min_value=14, max_value=30),
)
def test_hypothesis_simulation_invariants_hold(seed: int, num_farmers: int, season_days: int) -> None:
    config = ScenarioConfig(
        name="prop-test",
        season_length_days=season_days,
        district_size=DistrictSizeConfig(num_farmers=num_farmers),
    )
    # Test property on Baseline A
    strat_a = BaselineAStrategy()
    sim_a = DistrictSimulator(config=config, strategy=strat_a, seed=seed)
    state_a = sim_a.run()

    # Invariants for run
    assert state_a.total_acres > 0.0
    for f in state_a.fields:
        assert f.area_acres > 0.0
        assert not (f.is_cleared and f.is_burned)
        if f.is_cleared:
            assert f.cleared_at_day is not None
            assert f.cleared_at_day >= f.harvest_day
        if f.is_burned:
            assert f.burned_at_day is not None
            assert f.burned_at_day >= f.harvest_day

    # Straw deliveries never exceed total crop residue
    assert state_a.delivered_straw_tonnes <= state_a.total_straw_tonnes + 1e-4

    # Test property on Baseline B
    strat_b = BaselineBStrategy()
    sim_b = DistrictSimulator(config=config, strategy=strat_b, seed=seed)
    state_b = sim_b.run()

    assert state_b.total_acres > 0.0
    for f in state_b.fields:
        assert not (f.is_cleared and f.is_burned)
