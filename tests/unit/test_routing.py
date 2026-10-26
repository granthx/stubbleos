"""Unit tests for the OR-Tools VRP routing model and distance matrix providers."""

from uuid import uuid4

from stubbleos.optimization.routing import (
    BuyerDropoff,
    FieldPickup,
    HaversineDistanceMatrixProvider,
    OSRMClient,
    TruckSpec,
    solve_straw_routing,
)


def test_haversine_distance_matrix_provider() -> None:
    provider = HaversineDistanceMatrixProvider()
    locs = [(30.8, 75.8), (30.85, 75.85), (30.9, 75.9)]

    dist_mat, dur_mat = provider.get_distance_and_duration_matrix(locs, speed_kmh=40.0)

    assert len(dist_mat) == 3
    assert len(dur_mat) == 3
    assert dist_mat[0][0] == 0.0
    assert dist_mat[0][1] > 0.0
    # Symmetry
    assert abs(dist_mat[0][1] - dist_mat[1][0]) < 1e-4
    assert dur_mat[0][1] == dist_mat[0][1] / 40.0


def test_osrm_client_fallback_to_haversine_when_offline() -> None:
    # Pointing to a dead port triggers the transparent haversine fallback
    client = OSRMClient(base_url="http://127.0.0.1:59999", timeout_seconds=0.1)
    locs = [(30.8, 75.8), (30.85, 75.85)]

    dist_mat, _dur_mat = client.get_distance_and_duration_matrix(locs)
    assert len(dist_mat) == 2
    assert dist_mat[0][1] > 0.0


def test_straw_routing_truck_capacity_constraint() -> None:
    truck = TruckSpec(
        truck_id=uuid4(),
        capacity_tonnes=10.0,
        cost_per_km_inr=45.0,
        co2_kg_per_km=1.42,
        depot_lat=30.8,
        depot_lon=75.8,
    )
    buyer = BuyerDropoff(
        buyer_id=uuid4(),
        lat=30.9,
        lon=75.9,
        max_moisture_pct=16.0,
        capacity_tonnes=100.0,
    )
    # Field with 15 tonnes (exceeds single 10-tonne truck capacity)
    pickup = FieldPickup(
        field_id=uuid4(),
        lat=30.82,
        lon=75.82,
        tonnes=15.0,
        moisture_pct=14.0,
        deadline_hour=50.0,
    )

    out = solve_straw_routing(pickups=[pickup], dropoffs=[buyer], trucks=[truck])
    assert len(out.routes) == 1
    route = out.routes[0]
    assert route.delivered_tonnes <= truck.capacity_tonnes
    assert route.delivered_tonnes == 10.0


def test_straw_routing_moisture_spec_filtering() -> None:
    truck = TruckSpec(
        truck_id=uuid4(),
        capacity_tonnes=10.0,
        cost_per_km_inr=45.0,
        co2_kg_per_km=1.42,
        depot_lat=30.8,
        depot_lon=75.8,
    )
    # Biomass buyer with strict 16% max moisture
    buyer = BuyerDropoff(
        buyer_id=uuid4(),
        lat=30.9,
        lon=75.9,
        max_moisture_pct=16.0,
        capacity_tonnes=50.0,
    )
    # Field with wet straw at 24% moisture (exceeds buyer threshold)
    wet_pickup = FieldPickup(
        field_id=uuid4(),
        lat=30.82,
        lon=75.82,
        tonnes=8.0,
        moisture_pct=24.0,
        deadline_hour=50.0,
    )

    out = solve_straw_routing(pickups=[wet_pickup], dropoffs=[buyer], trucks=[truck])
    assert len(out.routes) == 0
    assert wet_pickup.field_id in out.unserved_field_ids
    assert out.solver_status == "ALL_PICKUPS_EXCEED_MOISTURE"
