# MRV Agent (Phase 4 Skeleton)

## Purpose
The MRV (Measurement, Reporting, and Verification) agent validates avoided stubble burning, estimates carbon dioxide equivalent (CO2e) emissions reductions, and produces cryptographically hashed impact evidence records (`indicative impact record (not registry-verified)`).

## Typed Contract
- Input: `MrvInput` (field ID, area acres, crop season, burn avoided boolean).
- Output: `MrvOutput` (`ImpactEstimate` with calculated CO2e avoided and SHA256 checksum).
- State: `MrvState`.

## Tools
- `generate_mrv_evidence_mock`: Calculates emissions avoided and generates cryptographic proof hashes.
