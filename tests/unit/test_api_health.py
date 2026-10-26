from fastapi.testclient import TestClient

from stubbleos.api.app import create_app
from stubbleos.core.config import Settings


def client(checks: dict[str, object]) -> TestClient:
    settings = Settings(_env_file=None, env="test", llm_provider="fake")  # type: ignore[call-arg]
    return TestClient(create_app(settings, readiness_checks=checks))  # type: ignore[arg-type]


def test_healthz() -> None:
    assert client({}).get("/healthz").json()["status"] == "ok"


def test_ready_when_all_checks_pass() -> None:
    r = client({"database": lambda: True, "redis": lambda: True}).get("/readyz")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_degraded_when_a_check_fails_or_raises() -> None:
    def boom() -> bool:
        raise ConnectionError("down")

    r = client({"database": lambda: True, "redis": boom}).get("/readyz")
    assert r.status_code == 503
    assert r.json()["checks"] == {"database": True, "redis": False}


def test_metrics_endpoint_exposes_prometheus_text() -> None:
    r = client({}).get("/metrics")
    assert r.status_code == 200
    assert "stubbleos_events_published_total" in r.text or "python_info" in r.text
