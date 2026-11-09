# StubbleOS

An autonomous coordination layer that connects farmers, machinery owners, logistics providers and straw buyers so that paddy straw in Punjab/Haryana is cleared before the wheat-sowing deadline without burning, with auditable impact records.

> **Status: simulation-first MVP.** Nothing here is deployed, piloted or validated with real farmers. Any data is synthetic and labeled as such. Impact records are *indicative, not registry-verified*.

## Results

The results below are produced by reproducible multi-seed simulation runs (`make results`):

### Baselines

The benchmark evaluates four coordination strategies implemented in `src/stubbleos/simulation/strategy.py`:

- **`baseline_a`**: An idealized, no-coordination-cost reference where farmers independently seek machines within a 12 km radius with a fixed 75% probability upon harvest or daily morning retries. Farmers query global district state directly with perfect real-time visibility into machine availability and GPS locations, booking the closest available machine with zero communication overhead and zero overhead latency (0.0 ms).
  TODO(author): Confirm whether baseline_a is intended as a frictionless theoretical upper bound or if realistic search friction (e.g., phone call delays, unobserved machines, booking rejections) should be introduced.
- **`baseline_b`**: A naive centralized First-Come-First-Served (FCFS) queue where harvested fields submit requests to a single district-wide FIFO queue with minimal overhead tracking (0.05 ms per event). Available machines are dispatched strictly in arrival order without geographic distance minimization, deadline urgency weighting, or landholding fairness.
- **`stubbleos_centralized`**: A centralized optimizer that batches pending unserviced fields and schedules idle machines using Google OR-Tools CP-SAT constraint programming, validated by Policy Guard checks. It optimizes for on-time clearance before sowing deadlines, smallholder fairness weighting, and minimal transit distances while recording actual solver wall-clock execution latency (695–1515 ms) and protocol messages.
- **`stubbleos_decentralized`**: A multi-agent decentralized coordinator using the Contract-Net Protocol (CNP) where harvested fields broadcast task announcements (CFPs) and idle machines submit bids based on marginal transit distance and schedule fit. Conflicts are resolved with smallholder fairness protection and deterministic tie-breaking, logging synthetic planning latency (0.5 ms per auction round, ~184 ms total).

### Benchmark Results

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

Legend: "Burn Reduction vs Baseline A" uses baseline_a as the reference, so negative means more burns than baseline_a.

### Interpreting These Results

Plainly and honestly, StubbleOS currently underperforms `baseline_a` across every evaluated scenario:
- **Clearance and Burn Reduction**: In all scenarios, `baseline_a` achieves higher clearance rates (99.5%–99.8%) and lower burn rates (0.59–1.72 burns/1k acres) than both StubbleOS strategies. `stubbleos_centralized` achieves 97.1%–99.3% clearance and 2.01–7.50 burns/1k acres (yielding negative "Burn Reduction vs Baseline A" figures from -38.4% to -683.1%), while `stubbleos_decentralized` clears ~89.9%–90.1% of fields with ~28.7–29.5 burns/1k acres (matching naive FCFS).
- **Straw Delivered**: `baseline_a` delivers significantly more straw (~700–736 tonnes) than `stubbleos_centralized` (60.7–142.1 tonnes) and `stubbleos_decentralized` (0.0–44.3 tonnes).
- **Supported Benefits**: The metrics support benefits only when comparing `stubbleos_centralized` against the naive FCFS queue (`baseline_b`) and on smallholder equity:
  - `stubbleos_centralized` drastically reduces burns compared to `baseline_b` (~2–7.5 vs ~29 burns/1k acres) and delivers more straw.
  - In `baseline-district`, `low-trust`, and `rain-shock`, `stubbleos_centralized` maintains a negative fairness gap (-0.20% to -0.74%), meaning smallholders achieve equal or slightly higher clearance rates than largeholders, whereas `baseline_b` and `stubbleos_decentralized` exhibit a +1.28% to +1.29% gap favoring largeholders.
  - `stubbleos_centralized` achieves slightly higher machine utilization (1.8%–5.1%) than `baseline_a` (1.3%–3.9%).

**What this comparison does and does not show**:
- *What it shows*: Structured centralized scheduling with CP-SAT (`stubbleos_centralized`) is vastly superior to uncoordinated FIFO queueing (`baseline_b`) in preventing fires, coordinating baler logistics, and safeguarding smallholder fairness.
- *What it does not show*: It does not show that StubbleOS outperforms an uncoordinated real-world market. In the simulator, `baseline_a` operates with zero communication latency and instantaneous, perfect information of all available machines within 12 km. By greedily locking in the nearest machine immediately upon harvest without batching delays or solver overhead, `baseline_a` acts as an idealized upper-bound reference rather than a realistic model of manual bilateral coordination.

**Overhead latency**:
Overhead latency measures computational wall-clock time spent computing schedules, running auctions, and validating policy guardrails. `baseline_a` records `0.0 ms` latency because it bypasses all coordination mechanisms, directly reading in-memory machine state. `stubbleos_centralized` records non-zero latency (695–1515 ms) because it executes OR-Tools CP-SAT constraint optimization, generates LLM schedule explanations, and checks safety policies across field batches. `stubbleos_decentralized` records ~184 ms from Contract-Net Protocol multi-agent auction bidding rounds.

**What would need to change before claiming an improvement**:
1. *Realistic baseline modeling*: `baseline_a` must incorporate real-world search friction, such as partial observability (farmers not knowing where machines are), phone-based inquiry latencies, booking rejections, and limited farmer search patience, rather than instantaneous global queries.
2. *Coordination-critical scenarios*: Benchmarks need scenarios where myopic local greedy dispatch fails, such as severe machine shortages, tight concurrent harvest peaks, clustered spatial demand, or cross-district logistics bottlenecks.
3. *Strategy dispatch improvements*: `stubbleos_centralized` currently batches assignments at daily boundaries, which delays machine assignment for newly harvested fields and increases burn risk; continuous or event-driven re-optimization would close this gap. Similarly, `stubbleos_decentralized` needs persistent booking confirmation mechanics so farmers do not burn during multi-round auctions.


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
| pytest suite (unit tests for config, events, bus, FakeLLM, prompts, schema, repositories, API, evals, go-live gate) | **Verified** (271/271 passed, 87% coverage) |
| `ruff`, `mypy --strict` | **Verified** (0 lint issues, 0 typing errors across source files) |
| Alembic baseline migration, audit-log trigger, CHECK constraints on real Postgres | **Verified logic** (needs Docker/PostGIS for integration test) |
| `RedisEventBus`, `AnthropicLLM` | **Verified in unit suite** (live checks require Redis / live key) |
| `docker compose up`, Dockerfile build | **Verified config** (`uv.lock` generated, `Dockerfile` switched to `uv sync --frozen`) |
