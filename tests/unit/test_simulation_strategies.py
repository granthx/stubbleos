"""Unit tests for coordination strategies: Baseline A, Baseline B, and StubbleOS stubs."""

import numpy as np

from stubbleos.core.types import FieldState, MachineStatus
from stubbleos.simulation.config import ScenarioConfig
from stubbleos.simulation.generator import generate_synthetic_district
from stubbleos.simulation.strategy import (
    BaselineAStrategy,
    BaselineBStrategy,
    StubbleOSCentralizedStrategy,
    StubbleOSDecentralizedStrategy,
)


def test_baseline_a_strategy_behavior() -> None:
    config = ScenarioConfig(name="test")
    state = generate_synthetic_district(config, seed=42)
    rng = np.random.default_rng(42)

    strategy = BaselineAStrategy(search_radius_km=15.0, p_seek_machine=1.0)
    strategy.initialize(state, rng)

    field = state.fields[0]
    field.state = FieldState.HARVESTED_RESIDUE_PRESENT

    # Since all machines are initially AVAILABLE, searching should find a machine
    machine = strategy.on_field_harvested(field, current_day=5.0)
    assert machine is not None
    assert strategy.has_confirmed_booking(field.field_id) is True

    # on_machine_available does nothing in Baseline A (uncoordinated)
    assert strategy.on_machine_available(machine, current_day=6.0) is None


def test_baseline_b_fcfs_queue_behavior() -> None:
    config = ScenarioConfig(name="test")
    state = generate_synthetic_district(config, seed=42)
    rng = np.random.default_rng(42)

    strategy = BaselineBStrategy()
    strategy.initialize(state, rng)

    # Harvest two fields
    field1 = state.fields[0]
    field2 = state.fields[1]
    field1.state = FieldState.HARVESTED_RESIDUE_PRESENT
    field2.state = FieldState.HARVESTED_RESIDUE_PRESENT

    # First field gets immediate idle machine
    m1 = strategy.on_field_harvested(field1, current_day=2.0)
    assert m1 is not None

    # Mark all machines as busy to test queueing
    for m in state.machines:
        m.status = MachineStatus.IN_USE

    m2 = strategy.on_field_harvested(field2, current_day=2.1)
    assert m2 is None
    assert strategy.has_confirmed_booking(field2.field_id) is True
    assert len(strategy.queue) == 1

    # Now free up a machine and check FCFS dispatch
    test_machine = state.machines[0]
    test_machine.status = MachineStatus.AVAILABLE

    assigned_field = strategy.on_machine_available(test_machine, current_day=2.5)
    assert assigned_field is not None
    assert assigned_field.field_id == field2.field_id
    assert len(strategy.queue) == 0


def test_stubbleos_strategies_behavior() -> None:
    config = ScenarioConfig(name="test")
    state = generate_synthetic_district(config, seed=42)
    rng = np.random.default_rng(42)

    field = state.fields[0]
    field.state = FieldState.HARVESTED_RESIDUE_PRESENT

    # Centralized Strategy
    centralized = StubbleOSCentralizedStrategy(time_limit_seconds=0.5)
    centralized.initialize(state, rng)
    assigned_m = centralized.on_field_harvested(field, current_day=1.0)
    assert centralized.has_confirmed_booking(field.field_id) is True
    assert assigned_m is not None

    # Decentralized Strategy
    decentralized = StubbleOSDecentralizedStrategy()
    decentralized.initialize(state, rng)
    m_award = decentralized.on_field_harvested(field, current_day=1.0)
    assert decentralized.has_confirmed_booking(field.field_id) is True
    assert m_award is not None
