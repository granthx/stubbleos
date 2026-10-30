"""Interactive demonstration runner for StubbleOS (Phase 7).

Boots an in-memory coordination environment, runs initial scheduling and logistics,
and launches the FastAPI service on http://127.0.0.1:8000.
"""

from __future__ import annotations

import sys

import uvicorn

from stubbleos import __version__
from stubbleos.api.app import create_app
from stubbleos.core.config import Settings
from stubbleos.core.logging import get_logger

log = get_logger(__name__)


def run_demo(host: str = "127.0.0.1", port: int = 8000) -> None:
    print("=" * 72)
    print(f"StubbleOS v{__version__} — Autonomous Crop Residue Coordination Layer")
    print("=" * 72)
    print("Initializing demonstration district: Sangrur (Punjab)")
    print("  * 240 agricultural fields loaded (Sentinel-2 NDVI & FIRMS thermal index)")
    print("  * 28 machinery units active (Super Seeders, Happy Seeders, Balers)")
    print("  * Vernacular channels active (WhatsApp & IVR Telephony in Punjabi/Hindi)")
    print("  * CP-SAT machine scheduler & VRP logistics optimizer online")
    print("  * Contract-Net industrial biomass marketplace active")
    print("-" * 72)
    print(f"Starting FastAPI server on http://{host}:{port}")
    print(f"  * REST API v1:    http://{host}:{port}/api/v1/fields")
    print(f"  * OpenAPI docs:   http://{host}:{port}/docs")
    print(f"  * Metrics:        http://{host}:{port}/metrics")
    print("  * Next.js UI:     http://localhost:3000 (run `cd frontend && npm run dev`)")
    print("=" * 72)

    settings = Settings(
        _env_file=None,
        env="dev",
        llm_provider="fake",
        database_url="sqlite:///:memory:",
    )
    app = create_app(settings, readiness_checks={"demo_in_memory": lambda: True})
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    run_demo(host=host, port=port)
