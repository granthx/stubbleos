# StubbleOS District Simulator Documentation

## 1. Overview & Architecture

The StubbleOS District Simulator is a discrete-event agricultural simulation engine built on **SimPy** (see [ADR-0001](file:///c:/Users/Granth/All%20project/stubbleos/stubbleos/docs/ADR/0001-simpy-over-mesa.md)). It simulates post-monsoon paddy harvest residue management across an Indian district (default: Ludhiana district, Punjab, India) during the tight 35-day window preceding rabi wheat sowing.

### Key Architectural Tenets
1. **Strict Determinism**: All stochasticity flows from a single run seed via NumPy `Generator` (`np.random.default_rng(seed)`) and `SeededUUIDFactory(seed)`. No calls to `time.time()`, `datetime.now()`, or unseeded `random` are permitted.
2. **SimClock Synchronization**: The simulation advances virtual time in hours (`env.now`). At critical events and daily boundaries, the deterministic `SimClock` is synchronized with `season_start + timedelta(hours=env.now)`.
3. **Synthetic Provenance**: All synthetic entities, database columns, and output metrics are explicitly labeled with `is_synthetic: true`.
4. **Reproducibility Guarantee**: The exact same configuration hash and run seed produces byte-identical metrics output across runs.

---

## 2. Core Modeling Assumptions

1. **Harvest & Deadline Dynamics**:
   - Harvest dates are distributed across the first 60% of the season.
   - Sowing deadlines are set 10 to 20 days after harvest. Fields not cleared by the deadline must be sown or farmers face steep winter yield penalties (~1% per day of delayed wheat sowing).
2. **Crop Residue Yield**:
   - Residue generation follows empirical Punjab agricultural benchmarks: 2.4 to 2.8 tonnes of paddy straw per acre.
3. **Spatial Distribution & Road Travel**:
   - Spatial coordinates are bound within real-world district bounds (Ludhiana: lat 30.72–30.98° N, lon 75.65–75.98° E).
   - Distances are computed using the great-circle Haversine formula augmented with a **1.3x road winding factor**.
4. **Weather (Rain Shocks)**:
   - Stochastic rain events halt machine field operations (soil saturation prevents heavy machinery and baled straw moisture exceeds factory acceptance thresholds).
5. **Machine Breakdown & Maintenance**:
   - Machines experience breakdown risks proportional to operating hours (~0.04/day rate), requiring exponential repair delays (mean ~20 hours).
6. **Farmer Urgency & Burn Decision Model**:
   - Without coordination or confirmed machine bookings, farmer anxiety accelerates quadratically as the deadline nears.
   - Trust scores (calibrated by landholding class and institutional confidence) dampen burn panic.
   - If a machine service is actively in progress, farmers never burn. If the deadline passes without clearance, farmers burn to prepare for wheat sowing.
7. **Commercial Straw Offtake**:
   - In-situ machines (Happy Seeder, Super Seeder) mulch residue directly into soil.
   - Ex-situ machines (Baler, Rake) produce baled straw transported by 10-tonne commercial trucks to nearby biomass power plants, compressed biogas (CBG) units, and paper mills.

---

## 3. Parameter Reference & Defaults

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `name` | string | required | Unique scenario identifier |
| `district_name` | string | `"ludhiana"` | Target district boundary |
| `season_start` | datetime (UTC) | `2026-10-15T00:00:00Z` | Start date of harvesting season |
| `season_length_days` | int | `35` | Duration of simulation window in days |
| `truck_count` | int | `25` | Number of commercial straw haulage trucks |
| **District Size** | | | |
| `num_farmers` | int | `150` | Total number of farm households |
| `fields_per_farmer_min` | int | `1` | Minimum fields operated per farmer |
| `fields_per_farmer_max` | int | `3` | Maximum fields operated per farmer |
| `landholding_distribution` | dict | `MARGINAL: 0.35, SMALL: 0.30, SEMI_MEDIUM: 0.20, MEDIUM: 0.12, LARGE: 0.03` | Landholding class proportions (Indian census) |
| **Machine Counts** | | | |
| `happy_seeder` | int | `15` | Dedicated in-situ seeding attachments |
| `super_seeder` | int | `20` | Combined rotary tiller and seed drill units |
| `baler` | int | `10` | Ex-situ straw baling units |
| `rake` | int | `10` | Swather / residue raking attachments |
| **Stochastic Parameters** | | | |
| `rain_shock_severity` | float | `0.15` | Probability factor controlling rain shock frequency |
| `rain_duration_hours_min` | float | `24.0` | Minimum duration of a rain window (hours) |
| `rain_duration_hours_max` | float | `48.0` | Maximum duration of a rain window (hours) |
| `machine_breakdown_rate_per_day` | float | `0.04` | Daily breakdown failure probability rate |
| `mean_repair_hours` | float | `20.0` | Mean time to repair broken machinery (hours) |
| `farmer_trust_mean` | float | `0.60` | Mean baseline trust score in formal coordination |
| `farmer_trust_std` | float | `0.15` | Standard deviation of farmer trust |
| `deadline_window_days_min` | int | `10` | Minimum post-harvest sowing window (days) |
| `deadline_window_days_max` | int | `20` | Maximum post-harvest sowing window (days) |
| **Buyer Specifications** | | | |
| `num_biomass_plants` | int | `2` | Commercial power plants procuring straw |
| `num_cbg_plants` | int | `2` | Compressed biogas production facilities |
| `num_paper_mills` | int | `1` | Pulp and paperboard mills |
| `target_total_demand_tonnes` | float | `15000.0` | Aggregate industrial straw demand (tonnes) |
| `price_inr_per_tonne_min` | float | `1500.0` | Minimum commercial gate purchase price (INR/tonne) |
| `price_inr_per_tonne_max` | float | `2200.0` | Maximum commercial gate purchase price (INR/tonne) |

---

## 4. Coordination Strategies

### Baseline A: No Coordination (Status Quo)
- Farmers act independently without central visibility or dispatch queues.
- Upon harvest, farmers phone nearby machine operators within a local search radius (default 12 km).
- If a machine is available, it is hired immediately. If no machine is free, the request fails with no queue.
- Farmers retry daily, but as sowing deadlines approach, panic burning increases sharply.

### Baseline B: First-Come-First-Served (FCFS Queue)
- Farmers register a clearing request upon harvest into a centralized district queue.
- As machines become idle or finish prior jobs, the coordinator dispatches them to the oldest unserved request in the queue.
- Having a queue position delays panic burning until the sowing deadline actually expires.

### StubbleOS Strategies (Phase 3 Stubs)
- `stubbleos_centralized`: Multi-depot Vehicle Routing Problem with Time Windows (VRPTW) optimization.
- `stubbleos_decentralized`: Peer-to-peer multi-agent auction and cooperative scheduling.
- Both raise `NotImplementedError` until Phase 3.

---

## 5. Metrics Pipeline & Statistical Methodology

For every simulation run, the following metrics are evaluated:
1. **% Fields Cleared Before Deadline**: Ratio of fields with `cleared_at_day <= sowing_deadline_day` to total fields.
2. **Burn Events per 1,000 Acres**: Number of burn events normalized per thousand acres of farmland.
3. **Machine Utilization & Idle Time**: Percentage of total capacity hours spent actively servicing fields vs sitting idle.
4. **Straw Tonnage Delivered & Fill Rate**: Total baled straw delivered to buyers and percentage of industrial demand satisfied.
5. **Farmer Net Income Delta**: Straw revenue minus machine rental fees and burn penalties, compared relative to Baseline A.
6. **Logistics Cost & Freight CO2**: Total truck transportation costs and diesel emissions (1.42 kg CO2 per truck-km).
7. **Fairness Gap**: The difference in clearance rate between largeholders (medium/large) and smallholders (marginal/small):
   $$\text{Fairness Gap} = \text{Clearance Rate}_{\text{large}} - \text{Clearance Rate}_{\text{small}}$$
8. **Coordination Overhead**: Communication message count, LLM calls, and algorithm planning latency.

### Multi-Seed Statistical Aggregation (95% Confidence Intervals)
Across $N$ runs (default 30 seeds), two distinct 95% confidence intervals are reported:
- **Parametric Student's t-interval**:
  $$\bar{x} \pm t_{n-1, 0.975} \cdot \frac{s}{\sqrt{n}}$$
- **Non-Parametric Bootstrap Percentile Interval**:
  Constructed from 10,000 resamples of sample means, computing the 2.5th and 97.5th percentiles.

Both intervals are reported side-by-side in `summary.json` and CLI output.

---

## 6. How to Reproduce

### Run a 30-Seed Simulation Experiment via CLI
```bash
# Run Baseline A on baseline district scenario
python -m stubbleos.simulation.run --scenario baseline-district --strategy baseline_a --seeds 30 --out results/

# Run Baseline B on machine scarce scenario
python -m stubbleos.simulation.run --scenario machine-scarce --strategy baseline_b --seeds 30 --out results/

# Run Baseline A on rain shock scenario
python -m stubbleos.simulation.run --scenario rain-shock --strategy baseline_a --seeds 30 --out results/

# Run Baseline B on low trust scenario
python -m stubbleos.simulation.run --scenario low-trust --strategy baseline_b --seeds 30 --out results/
```

### Determinism Verification
To verify byte-identical reproduction for the same seed and configuration:
```bash
uv run pytest tests/unit/test_simulation_determinism.py -v
```
