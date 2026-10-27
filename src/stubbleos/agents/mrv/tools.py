"""LangChain tools for MRV agent."""

from __future__ import annotations

import uuid
from typing import Any

from langchain_core.tools import tool

from stubbleos.agents.mrv.logic import generate_mrv_evidence, verify_evidence_tamper
from stubbleos.agents.mrv.schemas import EvidenceBundle, MrvInput
from stubbleos.data.repositories import AuditLogRepository, MrvRepository


@tool
def generate_mrv_evidence_mock(field_id_str: str, area_acres: float) -> dict[str, Any]:
    """Computes indicative CO2e avoided and produces SHA-256 evidence bundle."""
    f_uuid = uuid.UUID(field_id_str)
    inp = MrvInput(field_id=f_uuid, area_acres=area_acres, burn_avoided=True)
    out = generate_mrv_evidence(inp)
    return {
        "field_id": field_id_str,
        "co2e_kg_avoided": out.impact.co2e_kg_avoided,
        "burn_avoided": out.impact.burn_avoided,
        "sha256": out.evidence.sha256,
        "method_note": out.impact.method_note,
    }


@tool
def generate_mrv_bundle_tool(input_dict: dict[str, Any]) -> dict[str, Any]:
    """Calculates CO2e avoided and produces an auditable SHA-256 signed evidence bundle."""
    inp = MrvInput.model_validate(input_dict)
    out = generate_mrv_evidence(inp)
    return out.model_dump()


@tool
def verify_mrv_tamper_tool(evidence_dict: dict[str, Any]) -> dict[str, Any]:
    """Verifies that an MRV evidence bundle's content hash matches its inputs (tamper detection)."""
    bundle = EvidenceBundle.model_validate(evidence_dict)
    is_valid = verify_evidence_tamper(bundle)
    return {"is_valid": is_valid, "evidence_id": str(bundle.evidence_id)}


@tool
def persist_mrv_evidence_tool(
    output_dict: dict[str, Any],
    mrv_repo: MrvRepository | None = None,
    audit_repo: AuditLogRepository | None = None,
) -> dict[str, Any]:
    """Stores evidence and impact records into database tables and writes a hash-chained audit log."""
    from stubbleos.agents.mrv.schemas import MrvOutput

    out = MrvOutput.model_validate(output_dict)
    if mrv_repo is not None:
        mrv_repo.record_evidence(
            evidence_id=out.evidence.evidence_id,
            field_id=out.evidence.field_id,
            evidence_type=out.evidence.evidence_type,
            model_version=out.evidence.model_version,
            inputs=out.evidence.inputs,
            result=out.evidence.result,
            sha256=out.evidence.sha256,
            captured_at=out.evidence.captured_at,
            is_synthetic=out.evidence.is_synthetic,
        )
        mrv_repo.record_impact(
            record_id=out.impact.record_id,
            field_id=out.impact.field_id,
            season=out.impact.season,
            burn_avoided=out.impact.burn_avoided,
            area_acres=out.impact.area_acres,
            est_co2e_kg_avoided=out.impact.est_co2e_kg_avoided,
            method_note=out.impact.method_note,
            evidence_ids=out.impact.evidence_ids,
            record_sha256=out.impact.record_sha256,
            is_synthetic=out.impact.is_synthetic,
        )

    audit_id = None
    if audit_repo is not None:
        audit_entry = audit_repo.append(
            ts=out.evidence.captured_at,
            actor="mrv_agent",
            action="mrv_evidence_issued",
            entity_type="mrv_evidence",
            entity_id=str(out.evidence.evidence_id),
            details={
                "field_id": str(out.evidence.field_id),
                "burn_avoided": out.impact.burn_avoided,
                "co2e_kg_avoided": str(out.impact.est_co2e_kg_avoided),
                "evidence_sha256": out.evidence.sha256,
                "impact_sha256": out.impact.record_sha256,
            },
        )
        audit_id = audit_entry.id

    return {"status": "persisted", "audit_log_id": audit_id}


def create_mrv_tools(
    mrv_repo: MrvRepository | None = None,
    audit_repo: AuditLogRepository | None = None,
) -> list[Any]:
    """Factory to create MRV tools."""
    return [generate_mrv_evidence_mock]
