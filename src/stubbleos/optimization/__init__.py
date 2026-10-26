"""Optimization package for machine scheduling (CP-SAT) and logistics routing (VRPTW)."""

from stubbleos.optimization.routing import (
    BuyerDropoff,
    DistanceMatrixProvider,
    FieldPickup,
    HaversineDistanceMatrixProvider,
    OSRMClient,
    RouteStop,
    RoutingConfig,
    RoutingOutput,
    TruckRoute,
    TruckSpec,
    solve_straw_routing,
)
from stubbleos.optimization.scheduler import (
    JobRequest,
    MachineResource,
    OperatorResource,
    ScheduledAssignment,
    SchedulerConfig,
    SchedulerOutput,
    solve_schedule,
)

__all__ = [
    "BuyerDropoff",
    "DistanceMatrixProvider",
    "FieldPickup",
    "HaversineDistanceMatrixProvider",
    "JobRequest",
    "MachineResource",
    "OSRMClient",
    "OperatorResource",
    "RouteStop",
    "RoutingConfig",
    "RoutingOutput",
    "ScheduledAssignment",
    "SchedulerConfig",
    "SchedulerOutput",
    "TruckRoute",
    "TruckSpec",
    "solve_schedule",
    "solve_straw_routing",
]
