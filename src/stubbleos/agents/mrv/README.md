# MRV (Measurement, Reporting, and Verification) Agent

The **MRV Agent** verifies no-burn outcomes on agricultural fields and generates auditable, tamper-evident evidence bundles and indicative emissions reduction records.

## Responsibilities
- Fuses NASA FIRMS active fire hotspot detections with Sentinel-2 post-harvest clearance validation.
- Calculates estimated $CO_2e$ emissions avoided:
  $$\text{Emissions Avoided} = \text{Area (acres)} \times 1.8\,\text{tonnes/acre} \times 1000\,\text{kg/tonne} \times 1.46\,\text{kg CO}_2\text{e/kg} = 2628\,\text{kg CO}_2\text{e/acre}$$
- Produces an auditable `EvidenceBundle` containing canonical JSON input/result payloads and a deterministic SHA-256 content hash stored in the `mrv_evidence` database table.
- Issues an `IndicativeImpactRecord` strictly labeled `"indicative impact record (not registry-verified)"` stored in `impact_records`.
- Writes an append-only, cryptographic hash-chained audit record to the `audit_log` table.
