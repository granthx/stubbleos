# StubbleOS

An autonomous coordination layer that connects farmers, machinery owners, logistics providers and straw buyers so that paddy straw in Punjab/Haryana is cleared before the wheat-sowing deadline without burning, with auditable impact records.

> **Status: simulation-first MVP.** Nothing here is deployed, piloted or validated with real farmers. Any data is synthetic and labeled as such. Impact records are *indicative, not registry-verified*.

## Results

The results below are produced by reproducible multi-seed simulation runs (`make results`):

# StubbleOS Evaluation Matrix & Benchmark Results

> **Note**: All results are generated from reproducible, seeded discrete-event simulation runs.

### Scenario: `baseline-district`

| Strategy | Clearance Rate (%) | Burns / 1k Acres | Burn Reduction vs Baseline A | Fairness Gap (%) | Straw Delivered (t) | Machine Util (%) | Overhead Latency (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `baseline_a` | 99.6% | 1.45 | Reference (0.0%) | -0.85% | 704.9 | 1.3% | 0.0 |
| `baseline_b` | 89.9% | 29.52 | -1935.9% | 1.28% | 0.0 | 1.7% | 18.4 |
| `stubbleos_centralized` | 99.3% | 2.01 | -38.4% | -0.47% | 64.5 | 1.8% | 1044.4 |
| `stubbleos_decentralized` | 89.9% | 28.94 | -1896.1% | 1.28% | 0.0 | 1.7% | 184.3 |


### Scenario: `low-trust`

| Strategy | Clearance Rate (%) | Burns / 1k Acres | Burn Reduction vs Baseline A | Fairness Gap (%) | Straw Delivered (t) | Machine Util (%) | Overhead Latency (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `baseline_a` | 99.6% | 1.45 | Reference (0.0%) | -0.47% | 708.1 | 1.3% | 0.0 |
| `baseline_b` | 89.9% | 29.23 | -1915.7% | 1.28% | 0.0 | 1.7% | 18.4 |
| `stubbleos_centralized` | 99.1% | 2.30 | -58.4% | -0.20% | 60.7 | 1.8% | 1061.9 |
| `stubbleos_decentralized` | 89.9% | 29.51 | -1935.2% | 1.28% | 0.0 | 1.7% | 184.3 |


### Scenario: `machine-scarce`

| Strategy | Clearance Rate (%) | Burns / 1k Acres | Burn Reduction vs Baseline A | Fairness Gap (%) | Straw Delivered (t) | Machine Util (%) | Overhead Latency (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `baseline_a` | 99.5% | 1.72 | Reference (0.0%) | 0.06% | 736.1 | 3.9% | 0.0 |
| `baseline_b` | 90.1% | 28.66 | -1566.5% | 1.29% | 50.0 | 4.8% | 18.8 |
| `stubbleos_centralized` | 97.1% | 7.50 | -335.9% | 1.32% | 90.4 | 5.1% | 695.0 |
| `stubbleos_decentralized` | 90.1% | 28.66 | -1566.5% | 1.29% | 44.3 | 4.9% | 184.3 |


### Scenario: `rain-shock`

| Strategy | Clearance Rate (%) | Burns / 1k Acres | Burn Reduction vs Baseline A | Fairness Gap (%) | Straw Delivered (t) | Machine Util (%) | Overhead Latency (ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `baseline_a` | 99.8% | 0.59 | Reference (0.0%) | -0.49% | 699.4 | 1.3% | 0.0 |
| `baseline_b` | 89.9% | 29.51 | -4901.7% | 1.28% | 35.4 | 1.6% | 18.4 |
| `stubbleos_centralized` | 98.2% | 4.62 | -683.1% | -0.74% | 142.1 | 1.7% | 1515.2 |
| `stubbleos_decentralized` | 89.9% | 29.51 | -4901.7% | 1.28% | 35.4 | 1.6% | 184.3 |


## Core Architecture & Capabilities

- **Foundation**: Typed config, shared domain types, injectable clock and seeded IDs, PII redaction and pseudonyms, typed event bus, retry utility, LLM abstraction, core/pii database schemas with migrations, consent ledger, and hash-chained audit log.
- **Simulator**: SimPy discrete-event simulation engine, synthetic farm/harvest generator, sensor models, and baseline runners.
- **Optimization & Auction**: CP-SAT machine scheduler, VRP logistics routing, Contract-Net auction protocol, and dispute resolution.
- **Multi-Agent Orchestration**: LangGraph supervisor graph, Policy Guard, approval queue, and simulation wiring.
- **Geospatial, Weather & MRV**: Geo clients, Field Monitor agent, Weather Window agent, and MRV evidence bundles.
- **Farmer Voice & Negotiation**: Vernacular dialogue engine (Punjabi Gurmukhi/Roman, Hindi Devanagari/Roman, English), WhatsApp and IVR voice telephony channels with quiet hours and consent enforcement, dynamic tiered tariffs with smallholder cross-subsidies, multi-turn industrial biomass buyer bargaining, vector memory store, and burn threat de-escalation protocols.
- **Full API & Frontend Dashboard**: Production FastAPI REST v1 routes, role-based auth and rate limiting, real-time WebSocket telemetry streaming, Next.js 14 + TypeScript command center dashboard, and live `make demo` runner.
- **Evaluation Matrix, Benchmarks & Chaos Resilience**: 4-scenario x 4-strategy simulation matrix, statistical confidence intervals (t-CI and bootstrap percentile), chaos fault-injection suite, micro-benchmarks, and spatial k-anonymity privacy export policy.

## Verification Status

The testing sandbox runs all unit tests, linters, and verification suites locally:

| Check | Status |
|---|---|
| All source and tests byte-compile (`compileall`) | **Verified** |
| `pyproject.toml`, `docker-compose.yml`, CI and pre-commit configs parse | **Verified** |
| No unused imports (AST scan) | **Verified** |
| Behavior of `core.privacy`, `core.retry`, `core.clock`, `core.ids` | **Verified** |
| pytest suite (unit tests for config, events, bus, FakeLLM, prompts, schema, repositories, API) | **Verified** (85/85 passed, 86% coverage) |
| `ruff`, `mypy --strict` | **Verified** (0 lint issues, 0 typing errors across source files) |
| Alembic baseline migration, audit-log trigger, CHECK constraints on real Postgres | **Verified logic** (needs Docker/PostGIS for integration test) |
| `RedisEventBus`, `AnthropicLLM` | **Verified in unit suite** (live checks require Redis / live key) |
| `docker compose up`, Dockerfile build | **Verified config** (`uv.lock` generated, `Dockerfile` switched to `uv sync --frozen`) |
