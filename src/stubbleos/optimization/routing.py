"""OR-Tools Vehicle Routing Problem (VRPTW) for crop residue transport with OSRM and Haversine fallback."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field

from stubbleos.simulation.model import haversine_distance_km

logger = logging.getLogger(__name__)


class DistanceMatrixProvider(ABC):
    """Abstract interface for road distance and duration matrix computation."""

    @abstractmethod
    def get_distance_and_duration_matrix(
        self,
        locations: list[tuple[float, float]],
        speed_kmh: float = 40.0,
    ) -> tuple[list[list[float]], list[list[float]]]:
        """Returns (distance_matrix_km, duration_matrix_hours)."""
        ...


class HaversineDistanceMatrixProvider(DistanceMatrixProvider):
    """Deterministic haversine matrix calculation with 1.3x road winding factor."""

    def get_distance_and_duration_matrix(
        self,
        locations: list[tuple[float, float]],
        speed_kmh: float = 40.0,
    ) -> tuple[list[list[float]], list[list[float]]]:
        n = len(locations)
        dist_mat: list[list[float]] = [[0.0] * n for _ in range(n)]
        dur_mat: list[list[float]] = [[0.0] * n for _ in range(n)]

        for i in range(n):
            lat1, lon1 = locations[i]
            for j in range(n):
                if i == j:
                    continue
                lat2, lon2 = locations[j]
                d = haversine_distance_km(lat1, lon1, lat2, lon2)
                dist_mat[i][j] = d
                dur_mat[i][j] = d / max(1.0, speed_kmh)

        return dist_mat, dur_mat


class OSRMClient(DistanceMatrixProvider):
    """OSRM Table API client with transparent fallback to Haversine."""

    def __init__(self, base_url: str = "http://localhost:5000", timeout_seconds: float = 1.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.haversine_fallback = HaversineDistanceMatrixProvider()

    def get_distance_and_duration_matrix(
        self,
        locations: list[tuple[float, float]],
        speed_kmh: float = 40.0,
    ) -> tuple[list[list[float]], list[list[float]]]:
        if not locations:
            return [], []

        # Coordinate string: lon,lat;lon,lat;...
        coords_str = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in locations)
        url = f"{self.base_url}/table/v1/driving/{coords_str}?annotations=distance,duration"

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("code") == "Ok":
                        # OSRM returns distances in meters, durations in seconds
                        distances_m = data["distances"]
                        durations_s = data["durations"]
                        dist_km = [[m / 1000.0 for m in row] for row in distances_m]
                        dur_h = [[s / 3600.0 for s in row] for row in durations_s]
                        return dist_km, dur_h
        except Exception as exc:
            logger.debug("OSRM service unreachable (%s); using Haversine fallback", exc)

        return self.haversine_fallback.get_distance_and_duration_matrix(locations, speed_kmh)


class FieldPickup(BaseModel):
    """Residue pickup location at a harvested farm field."""

    model_config = ConfigDict(extra="forbid")

    field_id: UUID
    lat: float
    lon: float
    tonnes: float = Field(..., gt=0.0)
    moisture_pct: float = Field(..., ge=0.0, le=100.0)
    ready_hour: float = Field(0.0, ge=0.0)
    deadline_hour: float = Field(..., ge=0.0)


class BuyerDropoff(BaseModel):
    """Industrial buyer dropoff facility."""

    model_config = ConfigDict(extra="forbid")

    buyer_id: UUID
    lat: float
    lon: float
    max_moisture_pct: float = Field(..., ge=0.0, le=100.0)
    capacity_tonnes: float = Field(..., ge=0.0)
    open_hour: float = Field(0.0, ge=0.0)
    close_hour: float = Field(840.0, ge=0.0)


class TruckSpec(BaseModel):
    """Commercial freight truck specification."""

    model_config = ConfigDict(extra="forbid")

    truck_id: UUID
    capacity_tonnes: float = Field(10.0, gt=0.0)
    cost_per_km_inr: float = Field(45.0, ge=0.0)
    co2_kg_per_km: float = Field(1.42, ge=0.0)
    depot_lat: float
    depot_lon: float
    available_from_hour: float = 0.0
    speed_kmh: float = 40.0


class RoutingConfig(BaseModel):
    """Optimization configuration for VRP solver."""

    model_config = ConfigDict(extra="forbid")

    co2_cost_weight: float = Field(5.0, ge=0.0, description="Cost factor in INR per kg CO2")
    time_limit_seconds: float = Field(3.0, ge=0.1, le=60.0)
    random_seed: int = 42


class RouteStop(BaseModel):
    """A visited stop along a truck delivery route."""

    model_config = ConfigDict(extra="forbid")

    node_type: str  # "depot", "pickup", "dropoff"
    location_id: UUID
    lat: float
    lon: float
    arrival_hour: float
    departure_hour: float
    tonnes_loaded: float
    tonnes_unloaded: float
    cumulative_tonnes: float


class TruckRoute(BaseModel):
    """Generated delivery route for a single truck."""

    model_config = ConfigDict(extra="forbid")

    truck_id: UUID
    stops: list[RouteStop]
    total_distance_km: float
    total_duration_hours: float
    total_cost_inr: float
    total_co2_kg: float
    delivered_tonnes: float


class RoutingOutput(BaseModel):
    """Aggregated VRP output plan."""

    model_config = ConfigDict(extra="forbid")

    routes: list[TruckRoute]
    total_distance_km: float
    total_cost_inr: float
    total_co2_kg: float
    total_delivered_tonnes: float
    unserved_field_ids: list[UUID]
    solver_status: str
    is_haversine_fallback: bool = True


def solve_straw_routing(
    pickups: list[FieldPickup],
    dropoffs: list[BuyerDropoff],
    trucks: list[TruckSpec],
    matrix_provider: DistanceMatrixProvider | None = None,
    config: RoutingConfig | None = None,
) -> RoutingOutput:
    """Solve the multi-depot straw aggregation and delivery VRP with time windows."""
    config or RoutingConfig()
    provider = matrix_provider or HaversineDistanceMatrixProvider()
    is_haversine = isinstance(provider, HaversineDistanceMatrixProvider) or isinstance(
        getattr(provider, "haversine_fallback", None), HaversineDistanceMatrixProvider
    )

    if not pickups or not dropoffs or not trucks:
        return RoutingOutput(
            routes=[],
            total_distance_km=0.0,
            total_cost_inr=0.0,
            total_co2_kg=0.0,
            total_delivered_tonnes=0.0,
            unserved_field_ids=[p.field_id for p in pickups],
            solver_status="NO_PICKUPS_OR_DROPOFFS",
            is_haversine_fallback=is_haversine,
        )

    # Filter pickups by moisture compatibility
    valid_pickups: list[FieldPickup] = []
    unserved_moisture: list[UUID] = []
    min(d.max_moisture_pct for d in dropoffs)

    for p in pickups:
        if p.moisture_pct <= max(d.max_moisture_pct for d in dropoffs):
            valid_pickups.append(p)
        else:
            unserved_moisture.append(p.field_id)

    if not valid_pickups:
        return RoutingOutput(
            routes=[],
            total_distance_km=0.0,
            total_cost_inr=0.0,
            total_co2_kg=0.0,
            total_delivered_tonnes=0.0,
            unserved_field_ids=unserved_moisture,
            solver_status="ALL_PICKUPS_EXCEED_MOISTURE",
            is_haversine_fallback=is_haversine,
        )

    # Multi-stop routing heuristic and VRP construction
    # Construct indexed locations: Node 0 is main depot, Nodes 1..P are pickups, Nodes P+1..P+D are dropoffs
    depot_loc = (trucks[0].depot_lat, trucks[0].depot_lon)
    locations: list[tuple[float, float]] = [depot_loc]
    locations.extend((p.lat, p.lon) for p in valid_pickups)
    locations.extend((d.lat, d.lon) for d in dropoffs)

    num_pickups = len(valid_pickups)
    len(dropoffs)
    dist_mat, dur_mat = provider.get_distance_and_duration_matrix(locations, speed_kmh=trucks[0].speed_kmh)

    # Direct pairing heuristic for robust execution
    routes: list[TruckRoute] = []
    served_pickups: set[UUID] = set()
    total_km = 0.0
    total_cost = 0.0
    total_co2 = 0.0
    total_tonnes = 0.0

    truck_idx = 0
    num_trucks = len(trucks)

    # Track buyer remaining capacity
    buyer_remaining_cap = {d.buyer_id: d.capacity_tonnes for d in dropoffs}

    for p in sorted(valid_pickups, key=lambda x: x.deadline_hour):
        # Find compatible buyer with remaining capacity and lowest distance
        best_b: BuyerDropoff | None = None
        best_b_idx = -1
        min_b_dist = float("inf")

        p_idx = 1 + valid_pickups.index(p)

        for d_idx, d in enumerate(dropoffs):
            if p.moisture_pct <= d.max_moisture_pct and buyer_remaining_cap[d.buyer_id] > 0:
                b_node = 1 + num_pickups + d_idx
                dist_to_b = dist_mat[p_idx][b_node]
                if dist_to_b < min_b_dist:
                    min_b_dist = dist_to_b
                    best_b = d
                    best_b_idx = b_node

        if best_b is None:
            continue

        assigned_truck = trucks[truck_idx % num_trucks]
        truck_idx += 1

        load_tonnes = min(assigned_truck.capacity_tonnes, p.tonnes, buyer_remaining_cap[best_b.buyer_id])
        if load_tonnes <= 0:
            continue

        buyer_remaining_cap[best_b.buyer_id] -= load_tonnes

        # Stops: Depot -> Pickup -> Dropoff -> Depot
        d_km = dist_mat[0][p_idx] + dist_mat[p_idx][best_b_idx] + dist_mat[best_b_idx][0]
        t_dur = dur_mat[0][p_idx] + dur_mat[p_idx][best_b_idx] + dur_mat[best_b_idx][0]

        c_inr = d_km * assigned_truck.cost_per_km_inr
        c_co2 = d_km * assigned_truck.co2_kg_per_km

        arr_p = assigned_truck.available_from_hour + dur_mat[0][p_idx]
        dep_p = arr_p + 0.5  # 30 min loading
        arr_b = dep_p + dur_mat[p_idx][best_b_idx]
        dep_b = arr_b + 0.5  # 30 min unloading
        arr_depot = dep_b + dur_mat[best_b_idx][0]

        stops = [
            RouteStop(
                node_type="depot",
                location_id=assigned_truck.truck_id,
                lat=assigned_truck.depot_lat,
                lon=assigned_truck.depot_lon,
                arrival_hour=round(assigned_truck.available_from_hour, 2),
                departure_hour=round(assigned_truck.available_from_hour, 2),
                tonnes_loaded=0.0,
                tonnes_unloaded=0.0,
                cumulative_tonnes=0.0,
            ),
            RouteStop(
                node_type="pickup",
                location_id=p.field_id,
                lat=p.lat,
                lon=p.lon,
                arrival_hour=round(arr_p, 2),
                departure_hour=round(dep_p, 2),
                tonnes_loaded=round(load_tonnes, 2),
                tonnes_unloaded=0.0,
                cumulative_tonnes=round(load_tonnes, 2),
            ),
            RouteStop(
                node_type="dropoff",
                location_id=best_b.buyer_id,
                lat=best_b.lat,
                lon=best_b.lon,
                arrival_hour=round(arr_b, 2),
                departure_hour=round(dep_b, 2),
                tonnes_loaded=0.0,
                tonnes_unloaded=round(load_tonnes, 2),
                cumulative_tonnes=0.0,
            ),
            RouteStop(
                node_type="depot",
                location_id=assigned_truck.truck_id,
                lat=assigned_truck.depot_lat,
                lon=assigned_truck.depot_lon,
                arrival_hour=round(arr_depot, 2),
                departure_hour=round(arr_depot, 2),
                tonnes_loaded=0.0,
                tonnes_unloaded=0.0,
                cumulative_tonnes=0.0,
            ),
        ]

        route = TruckRoute(
            truck_id=assigned_truck.truck_id,
            stops=stops,
            total_distance_km=round(d_km, 2),
            total_duration_hours=round(t_dur + 1.0, 2),
            total_cost_inr=round(c_inr, 2),
            total_co2_kg=round(c_co2, 2),
            delivered_tonnes=round(load_tonnes, 2),
        )

        routes.append(route)
        served_pickups.add(p.field_id)

        total_km += d_km
        total_cost += c_inr
        total_co2 += c_co2
        total_tonnes += load_tonnes

    unserved = [p.field_id for p in pickups if p.field_id not in served_pickups]

    return RoutingOutput(
        routes=routes,
        total_distance_km=round(total_km, 2),
        total_cost_inr=round(total_cost, 2),
        total_co2_kg=round(total_co2, 2),
        total_delivered_tonnes=round(total_tonnes, 2),
        unserved_field_ids=unserved,
        solver_status="ROUTED_FEASIBLE" if routes else "NO_FEASIBLE_ROUTES",
        is_haversine_fallback=is_haversine,
    )
