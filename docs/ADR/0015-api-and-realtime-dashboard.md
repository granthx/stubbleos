# ADR 0015: REST API Architecture and Real-Time Operations Dashboard

**Status:** accepted (Phase 7)  
**Date:** 2026-10-30  
**Context:** StubbleOS Phase 7 (Full API & Frontend Dashboard)

## Context

Previous phases established the discrete event simulator, OR-Tools optimizers, LangGraph supervisor agents, geospatial monitors, and vernacular dialogue channels. To operate effectively in the field during the compressed 20-day stubble burning window, district administration officers, Custom Hiring Centre (CHC) operators, and industrial biomass buyers require:
1. A robust, authenticated REST API exposing all system aggregates and actions.
2. Low-latency real-time telemetry streaming for machine route tracking and fire detection alerts.
3. An intuitive, responsive command center UI visualizing spatial field states, fleet dispatch schedules, and human-in-the-loop (HITL) approval queues.

## Decision

1. **FastAPI REST v1 Routing & Security**:
   - Structured routers under `/api/v1` for `fields`, `machines`, `plans`, `bookings`, `approvals`, `contracts`, `channels`, `mrv`, and `district-summary`.
   - Role-Based Access Control (`Role.ADMIN`, `Role.OPERATOR`, `Role.FARMER`, `Role.BUYER`) enforced via `X-API-Key` headers.
   - Sliding-window rate limiting dependency to safeguard critical services during peak crisis hours.
   - CORS middleware enabled for cross-origin frontend dashboard integration.

2. **WebSocket Telemetry Streaming**:
   - WebSocket connection manager at `/ws/district/{district}`.
   - Bridges the core `EventBus` (`*` wildcard listener) directly to connected dashboard clients, streaming field state changes, burn detections, machine GPS updates, and approval requests.

3. **Next.js 14 / TypeScript Operations Dashboard**:
   - Built with Next.js App Router, TypeScript, and Tailwind CSS.
   - **District Command Center**:
     - Live KPI header displaying clearance %, avoided CO2e tonnes, and active fire warnings.
     - Interactive Geospatial Map rendering agricultural parcels color-coded by Sentinel-2 NDVI and NASA FIRMS thermal detections.
     - Active Machine Fleet dispatch table with operator tracking and daily throughput.
     - HITL approval queue enabling 1-click administrative review of solver replans and urgent farmer burn threats.
     - Contract-Net biomass off-take marketplace order book.
     - Bilingual farmer voice & WhatsApp dialogue feed (Punjabi and Hindi).
   - Resilience: Provides automatic fallback to rich synthetic mock streams if the backend server is temporarily unreachable.

4. **Demonstration Harness**:
   - `stubbleos.demo` module launches the complete in-memory environment, accessible via `make demo`.

## Consequences

- District officers and equipment operators have complete, real-time situational awareness.
- Administrative interventions (approvals/rejections) synchronize with the agent orchestrator within milliseconds.
- Third-party aggregators and carbon registries can programmatically query indicative MRV proofs and SHA-256 integrity hashes.
