"""District simulator package for crop residue coordination."""

from stubbleos.simulation.config import (
    BuyerSpecConfig,
    DistrictSizeConfig,
    MachineCountsConfig,
    ScenarioConfig,
    StochasticParamsConfig,
)
from stubbleos.simulation.generator import generate_synthetic_district
from stubbleos.simulation.metrics import (
    AggregatedMetric,
    AggregatedSimulationReport,
    SimulationRunMetrics,
    aggregate_seed_metrics,
    compute_confidence_intervals,
    compute_run_metrics,
)
from stubbleos.simulation.model import (
    DistrictState,
    SimulatedBuyer,
    SimulatedFarmer,
    SimulatedField,
    SimulatedMachine,
    SimulatedOperator,
    SimulatedTruck,
    haversine_distance_km,
)
from stubbleos.simulation.sensor import (
    DistrictSensorModel,
    SensorConfig,
    SyntheticObservation,
)
from stubbleos.simulation.simulator import DistrictSimulator
from stubbleos.simulation.stochastic import (
    RainSchedule,
    generate_rain_schedule,
    sample_machine_breakdown,
    should_farmer_burn,
)
from stubbleos.simulation.strategy import (
    BaselineAStrategy,
    BaselineBStrategy,
    CoordinationStrategy,
    StubbleOSCentralizedStrategy,
    StubbleOSDecentralizedStrategy,
)

__all__ = [
    "AggregatedMetric",
    "AggregatedSimulationReport",
    "BaselineAStrategy",
    "BaselineBStrategy",
    "BuyerSpecConfig",
    "CoordinationStrategy",
    "DistrictSensorModel",
    "DistrictSimulator",
    "DistrictSizeConfig",
    "DistrictState",
    "MachineCountsConfig",
    "RainSchedule",
    "ScenarioConfig",
    "SensorConfig",
    "SimulatedBuyer",
    "SimulatedFarmer",
    "SimulatedField",
    "SimulatedMachine",
    "SimulatedOperator",
    "SimulatedTruck",
    "SimulationRunMetrics",
    "StochasticParamsConfig",
    "StubbleOSCentralizedStrategy",
    "StubbleOSDecentralizedStrategy",
    "SyntheticObservation",
    "aggregate_seed_metrics",
    "compute_confidence_intervals",
    "compute_run_metrics",
    "generate_rain_schedule",
    "generate_synthetic_district",
    "haversine_distance_km",
    "sample_machine_breakdown",
    "should_farmer_burn",
]
