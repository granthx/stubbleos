# MRV Methodology Gap Analysis

> [!CAUTION]
> **LEGAL AND REGULATORY DISCLAIMER**
> StubbleOS issues **indicative impact records only** (`indicative impact record (not registry-verified)`).
> **NONE** of the emissions reductions calculated or stored in StubbleOS are certified, registered, or tradable as carbon offsets or credits on Verra (VCS), Gold Standard, CDM, Article 6.4, or any national or international carbon registry.

---

## Executive Summary

While StubbleOS implements cryptographic content hashing (SHA-256), sensor fusion (Sentinel-2 L2A optical + NASA FIRMS VIIRS active fire data), and append-only database audit logging (`audit_log` with hash chains), these mechanisms fulfill internal operational traceability for farmer cooperatives and FPOs—**not** compliance with verified carbon crediting methodologies.

A real voluntary carbon market (VCM) carbon crediting methodology (such as **Verra VM0042** *Improved Agricultural Land Management* or related avoided-biomass burning methodologies) demands rigorous methodological guarantees that StubbleOS deliberately does not claim.

---

## Key Methodological Gaps

### 1. Baseline Scenario & Historical Counterfactual
- **Registry Standard**: Requires a minimum 3- to 5-year historical remote sensing and ground-truthed baseline establishing regional burning rates, tillage practices, and crop residue fates in the absence of the project intervention. Dynamic baselines must adjust for weather shocks and macro-economic commodity shifts.
- **StubbleOS Reality**: Uses a static synthetic simulation baseline or single-season default counterfactual assuming residue burning if not cleared within the sowing window.

### 2. Additionality Assessment
- **Registry Standard**: Demands strict regulatory and financial additionality testing:
  - *Regulatory Additionality*: Confirming the action is not legally mandated (or demonstrating that existing anti-burning laws in Punjab/Haryana suffer widespread non-enforcement above documented baseline thresholds).
  - *Financial & Investment Barrier Analysis*: Demonstrating that without carbon finance, custom hiring centers (CHCs) and smallholder farmers would face prohibitive financial barriers to adopting Happy Seeders or baling machinery.
  - *Common Practice Analysis*: Proving the intervention rate substantially exceeds prevailing regional adoption.
- **StubbleOS Reality**: Does not conduct investment barrier testing or common practice audits; operates as a coordination and logistics dispatch platform.

### 3. Permanence and Reversal Risk
- **Registry Standard**:
  - In agricultural carbon projects (soil organic carbon or avoided emissions), reversals can occur if farmers switch back to burning or deep moldboard plowing in subsequent seasons.
  - Requires risk buffer pool deductions (typically 10–25% of issued credits held in an escrow buffer) and long-term monitoring plans (10 to 30 years).
- **StubbleOS Reality**: Records operate on a single harvest season horizon (`2026_kharif`). No reversal buffer pool is maintained or claimed.

### 4. Leakage Accounting
- **Registry Standard**:
  - *Activity Shifting Leakage*: Verifying that machinery subsidized in the project district did not displace machinery from adjacent districts, thereby causing burning to increase elsewhere.
  - *Market Leakage*: Analyzing whether biomass off-take (e.g. for CBG or biomass pellets) caused emissions elsewhere in the supply chain.
  - *Emissions from Machinery & Haulage*: Netting out diesel emissions from tractors, balers, and transport trucks from gross avoided emissions.
- **StubbleOS Reality**: Haulage fuel and $CO_2$ are estimated for logistical optimization, but are not audited against full lifecycle greenhouse gas (GHG) accounting standards (ISO 14064-2 / GHG Protocol).

### 5. Uncertainty & Measurement Precision
- **Registry Standard**:
  - Optical satellite observations suffer from cloud cover occlusion during post-harvest windows.
  - NASA FIRMS VIIRS has spatial scan/track footprint limitations (~375 m resolution) and may miss brief daytime fires or under-canopy smoldering.
  - Requires statistical uncertainty deductions if measurement error exceeds specified methodology precision thresholds ($\pm 10\%$ at 90% confidence).
- **StubbleOS Reality**: Flags low confidence and routes to human coordinator approval, but does not apply statistical confidence band discount factors to calculated tonnage.

### 6. Independent Third-Party Validation and Verification (VVB)
- **Registry Standard**:
  - Independent accredited Validation and Verification Bodies (VVBs like TÜV, DNV, Epic Sustainability) must conduct on-site physical audits, interview farmers, inspect machinery logs, and audit remote sensing algorithms.
- **StubbleOS Reality**: Relies on automated LangGraph agent evaluation and local cooperative coordinator approvals. No third-party VVB audit is conducted or claimed.

---

## Comparison Matrix

| Registry Requirement | Standard Voluntary Carbon Market (VCM) | StubbleOS Implementation | Compliance Status |
| :--- | :--- | :--- | :--- |
| **Methodology** | Verra VM0042 / Gold Standard Agri | Pure empirical factor ($1.8\,\text{t/ac} \times 1.46\,\text{kg CO}_2\text{e}$) | ❌ Not Certified |
| **Baseline** | 3–5 yr historical satellite + field baseline | Simulated counterfactual | ❌ Not Compliant |
| **Additionality** | Financial barrier & common practice audit | None | ❌ Not Claimed |
| **Permanence** | 10–30 year buffer pool reserve | Single-season operational verification | ❌ Not Claimed |
| **Leakage** | Supply chain displacement & diesel subtraction | Logistical routing cost estimate only | ❌ Not Compliant |
| **Verification** | Accredited independent VVB on-site audit | Cooperative coordinator approval queue | ❌ Internal Only |
| **Data Integrity** | Registry ledger issuance serial numbers | SHA-256 evidence bundle + `audit_log` hash-chain | ✔️ Internal Audit Ready |

---

## Purpose of StubbleOS Impact Records

StubbleOS indicative impact records serve strictly internal coordination objectives:
1. **FPO Member Tracking**: Providing cooperative leaders with transparent visibility into which member fields avoided burning.
2. **Cooperative Incentive Allocation**: Enabling local FPOs to disburse machinery fee discounts or cooperative rebates.
3. **Logistics Retrospective**: Measuring district-wide progress year-over-year in reducing crop residue burning.
