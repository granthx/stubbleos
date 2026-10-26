"""Logic and emissions avoidance verification for MRV agent."""

from __future__ import annotations

import hashlib
import json

from stubbleos.agents.mrv.schemas import ImpactEstimate, MrvInput, MrvOutput


def compute_mrv_evidence(input_data: MrvInput) -> MrvOutput:
    """Computes indicative CO2e avoided and signs proof with SHA256."""
    # Empirical standard: 1 acre paddy yields ~1.8 tonnes residue;
    # burning 1 kg residue emits ~1.46 kg CO2e.
    # Avoided emissions = 1.8 * 1000 * 1.46 = ~2628 kg CO2e / acre.
    co2e_avoided = input_data.area_acres * 1.8 * 1000.0 * 1.46 if input_data.burn_avoided else 0.0

    raw_payload = {
        "field_id": str(input_data.field_id),
        "area_acres": input_data.area_acres,
        "season": input_data.season,
        "burn_avoided": input_data.burn_avoided,
        "co2e_kg_avoided": round(co2e_avoided, 2),
    }
    sha = hashlib.sha256(json.dumps(raw_payload, sort_keys=True).encode("utf-8")).hexdigest()

    impact = ImpactEstimate(
        burn_avoided=input_data.burn_avoided,
        area_acres=round(input_data.area_acres, 2),
        co2e_kg_avoided=round(co2e_avoided, 2),
        record_sha256=sha,
    )
    return MrvOutput(field_id=input_data.field_id, impact=impact)
