"""Unit tests for REST API v1 endpoints and WebSockets."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from stubbleos.api.app import create_app
from stubbleos.core.config import Settings
from stubbleos.core.types import FieldState


@pytest.fixture
def client() -> TestClient:
    settings = Settings(_env_file=None, env="test", llm_provider="fake")  # type: ignore[call-arg]
    app = create_app(settings, readiness_checks={})
    return TestClient(app)


def test_list_and_filter_fields(client: TestClient) -> None:
    res = client.get("/api/v1/fields?district=sangrur")
    assert res.status_code == 200
    fields = res.json()
    assert len(fields) > 0
    assert fields[0]["district"] == "sangrur"

    # Filter by state
    res_cleared = client.get(f"/api/v1/fields?district=sangrur&state={FieldState.CLEARED.value}")
    assert res_cleared.status_code == 200
    for f in res_cleared.json():
        assert f["state"] == FieldState.CLEARED.value


def test_register_and_get_field(client: TestClient) -> None:
    f_id = uuid.uuid4()
    req = {
        "farmer_id": str(f_id),
        "district": "sangrur",
        "village_code": "PB-SAN-NEW",
        "area_acres": 4.5,
        "center_lat": 30.260,
        "center_lon": 75.860,
        "crop_type": "paddy",
    }
    # Register field with admin key
    res = client.post("/api/v1/fields", json=req, headers={"X-API-Key": "stubbleos-admin-key"})
    assert res.status_code == 201
    created = res.json()
    assert created["village_code"] == "PB-SAN-NEW"
    assert created["area_acres"] == 4.5

    # Fetch created field
    res_get = client.get(f"/api/v1/fields/{created['id']}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == created["id"]


def test_list_machines(client: TestClient) -> None:
    res = client.get("/api/v1/machines?district=sangrur")
    assert res.status_code == 200
    machines = res.json()
    assert len(machines) > 0
    assert "machine_type" in machines[0]
    assert "capacity_acres_per_day" in machines[0]


def test_plans_and_replan_trigger(client: TestClient) -> None:
    res = client.get("/api/v1/plans?district=sangrur")
    assert res.status_code == 200
    plans = res.json()
    assert len(plans) > 0
    assert plans[0]["strategy"] == "stubbleos_centralized_cpsat"

    # Trigger emergency replan
    replan_req = {
        "district": "sangrur",
        "reason": "Unexpected rain forecast change",
        "emergency": True,
    }
    res_replan = client.post(
        "/api/v1/plans/replan",
        json=replan_req,
        headers={"X-API-Key": "stubbleos-admin-key"},
    )
    assert res_replan.status_code == 200
    new_plan = res_replan.json()
    assert "emergency" in new_plan["strategy"]


def test_bookings_create_and_confirm(client: TestClient) -> None:
    req = {
        "farmer_id": str(uuid.uuid4()),
        "field_id": str(uuid.uuid4()),
        "service_type": "in_situ_sowing",
        "machine_type": "super_seeder",
        "target_date": "2026-11-03",
        "channel": "whatsapp",
    }
    res = client.post("/api/v1/bookings", json=req)
    assert res.status_code == 201
    booking = res.json()
    assert booking["status"] == "proposed"

    # Confirm booking
    res_conf = client.post(f"/api/v1/bookings/{booking['id']}/confirm")
    assert res_conf.status_code == 200
    assert res_conf.json()["status"] == "confirmed"


def test_approvals_listing_and_resolution(client: TestClient) -> None:
    res = client.get("/api/v1/approvals")
    assert res.status_code == 200
    approvals = res.json()
    assert len(approvals) > 0
    a_id = approvals[0]["id"]

    # Resolve approval
    res_resolve = client.post(
        f"/api/v1/approvals/{a_id}/resolve",
        json={"decision": "approved", "note": "Verified by district officer"},
        headers={"X-API-Key": "stubbleos-operator-key"},
    )
    assert res_resolve.status_code == 200
    resolved = res_resolve.json()
    assert resolved["status"] == "approved"
    assert resolved["decided_by_role"] == "operator"


def test_contract_bidding_and_acceptance(client: TestClient) -> None:
    b_id = uuid.uuid4()
    bid = {
        "buyer_id": str(b_id),
        "order_id": str(uuid.uuid4()),
        "price_per_tonne_inr": 1750.0,
        "tonnes": 50.0,
        "delivery_term": "ex_field",
        "moisture_max_pct": 14.0,
    }
    res = client.post(
        "/api/v1/contracts/negotiate",
        json=bid,
        headers={"X-API-Key": "stubbleos-buyer-key"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["counter_offer"]["accepted"] is True
    assert data["contract"] is not None

    contract_id = data["contract"]["id"]
    res_accept = client.post(
        f"/api/v1/contracts/{contract_id}/accept",
        headers={"X-API-Key": "stubbleos-buyer-key"},
    )
    assert res_accept.status_code == 200
    assert res_accept.json()["status"] == "accepted"


def test_channel_webhooks(client: TestClient) -> None:
    # WhatsApp inbound webhook
    wa_payload = {
        "sender_id": "+919876543210",
        "text": "ਮੈਨੂੰ ਮਸ਼ੀਨ ਚਾਹੀਦੀ ਹੈ",
    }
    res_wa = client.post("/api/v1/channels/webhook/whatsapp", json=wa_payload)
    assert res_wa.status_code == 200
    assert res_wa.json()["status"] == "received"

    # IVR inbound webhook
    ivr_payload = {
        "From": "+919876543210",
        "Digits": "1",
    }
    res_ivr = client.post("/api/v1/channels/webhook/voice", json=ivr_payload)
    assert res_ivr.status_code == 200
    assert res_ivr.json()["status"] == "received"


def test_mrv_and_district_summary(client: TestClient) -> None:
    # MRV endpoint
    fld_id = uuid.uuid4()
    res_mrv = client.get(f"/api/v1/mrv/{fld_id}")
    assert res_mrv.status_code == 200
    proof = res_mrv.json()
    assert "co2e_avoided_tonnes" in proof
    assert len(proof["bundle_sha256"]) == 64
    assert proof["impact_label"] == "indicative impact record (not registry-verified)"

    # District summary endpoint
    res_dist = client.get("/api/v1/district-summary/sangrur")
    assert res_dist.status_code == 200
    summary = res_dist.json()
    assert summary["district"] == "sangrur"
    assert summary["total_fields"] >= 0
    assert summary["indicative_co2e_avoided_tonnes"] >= 0.0


def test_websocket_connection_and_echo(client: TestClient) -> None:
    with client.websocket_connect("/ws/district/sangrur") as websocket:
        websocket.send_text("ping")
        data = websocket.receive_json()
        assert data["type"] == "ack"
        assert data["received"] == "ping"
