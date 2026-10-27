"""Pure logic and cryptographic hash verification for MRV evidence bundles."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any
from uuid import NAMESPACE_DNS, uuid5

from stubbleos.agents.mrv.schemas import (
    EvidenceBundle,
    IndicativeImpactRecord,
    MrvInput,
    MrvOutput,
)
from stubbleos.core.clock import IST


def compute_canonical_hash(payload: dict[str, Any]) -> str:
    """Computes deterministic SHA-256 hash using sorted canonical JSON representation."""
    canonical_str = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


def verify_evidence_tamper(evidence: EvidenceBundle) -> bool:
    """Verifies that the content hash matches the inputs and results (detects tampering)."""
    payload = {
        "evidence_type": evidence.evidence_type,
        "model_version": evidence.model_version,
        "field_id": str(evidence.field_id),
        "inputs": evidence.inputs,
        "result": evidence.result,
        "captured_at": evidence.captured_at.isoformat(),
    }
    expected_hash = compute_canonical_hash(payload)
    return expected_hash == evidence.sha256


def generate_mrv_evidence(input_data: MrvInput) -> MrvOutput:
    """Synthesizes satellite and thermal data into auditable evidence and an indicative impact record."""
    now = input_data.captured_at or datetime.now(IST)

    # Verification decision: no FIRMS fire hits AND satellite confirmed clearance
    burn_avoided = (
        input_data.burn_avoided
        and (input_data.firms_hotspots_detected == 0)
        and input_data.satellite_cleared_confirmed
    )

    # Empirical factors: 1.8 tonnes residue / acre; 1 kg residue = 1.46 kg CO2e
    co2e_kg_avoided = round(input_data.area_acres * 1.8 * 1000.0 * 1.46, 2) if burn_avoided else 0.0

    inputs_dict = {
        "field_id": str(input_data.field_id),
        "area_acres": input_data.area_acres,
        "season": input_data.season,
        "firms_hotspots_detected": input_data.firms_hotspots_detected,
        "satellite_cleared_confirmed": input_data.satellite_cleared_confirmed,
        "satellite_scene_ids": input_data.satellite_scene_ids,
    }

    results_dict = {
        "burn_avoided": burn_avoided,
        "co2e_kg_avoided": co2e_kg_avoided,
        "verification_status": "verified_no_burn" if burn_avoided else "burn_unverified",
    }

    # Deterministic evidence SHA-256 hash
    evidence_payload = {
        "evidence_type": "sentinel2_firms_fusion",
        "model_version": input_data.algorithm_version,
        "field_id": str(input_data.field_id),
        "inputs": inputs_dict,
        "result": results_dict,
        "captured_at": now.isoformat(),
    }
    evidence_sha = compute_canonical_hash(evidence_payload)
    evidence_id = uuid5(NAMESPACE_DNS, f"evidence:{evidence_sha}")

    evidence_bundle = EvidenceBundle(
        evidence_id=evidence_id,
        field_id=input_data.field_id,
        evidence_type="sentinel2_firms_fusion",
        model_version=input_data.algorithm_version,
        inputs=inputs_dict,
        result=results_dict,
        sha256=evidence_sha,
        captured_at=now,
        is_synthetic=True,
    )

    # Indicative Impact Record
    impact_payload = {
        "field_id": str(input_data.field_id),
        "season": input_data.season,
        "burn_avoided": burn_avoided,
        "area_acres": round(input_data.area_acres, 4),
        "est_co2e_kg_avoided": round(co2e_kg_avoided, 4),
        "evidence_sha256": evidence_sha,
    }
    impact_sha = compute_canonical_hash(impact_payload)
    impact_id = uuid5(NAMESPACE_DNS, f"impact:{impact_sha}")

    impact_record = IndicativeImpactRecord(
        record_id=impact_id,
        field_id=input_data.field_id,
        season=input_data.season,
        label="indicative impact record (not registry-verified)",
        burn_avoided=burn_avoided,
        area_acres=round(input_data.area_acres, 2),
        est_co2e_kg_avoided=co2e_kg_avoided,
        evidence_ids=[str(evidence_id)],
        record_sha256=impact_sha,
        is_synthetic=True,
    )

    return MrvOutput(
        field_id=input_data.field_id,
        evidence=evidence_bundle,
        impact=impact_record,
    )


# Backward compatible alias
compute_mrv_evidence = generate_mrv_evidence
