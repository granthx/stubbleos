"""LangGraph definition for MRV agent."""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from stubbleos.agents.mrv.logic import generate_mrv_evidence
from stubbleos.agents.mrv.schemas import MrvState
from stubbleos.data.repositories import AuditLogRepository, MrvRepository


def build_mrv_graph(
    *,
    mrv_repo: MrvRepository | None = None,
    audit_repo: AuditLogRepository | None = None,
    checkpointer: Any | None = None,
) -> Any:
    """Builds and compiles the MRV agent LangGraph."""

    def generation_node(state: MrvState) -> dict[str, Any]:
        output = generate_mrv_evidence(state.input)
        return {"output": output, "status": "generated"}

    def persist_and_audit_node(state: MrvState) -> dict[str, Any]:
        if state.output is None:
            return {"status": "error_no_output"}

        out = state.output
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

        updated_output = out.model_copy(update={"audit_log_id": audit_id})
        return {
            "output": updated_output,
            "persisted_to_db": True,
            "status": "completed",
        }

    builder = StateGraph(MrvState)
    builder.add_node("generation", generation_node)
    builder.add_node("persist_and_audit", persist_and_audit_node)

    builder.set_entry_point("generation")
    builder.add_edge("generation", "persist_and_audit")
    builder.add_edge("persist_and_audit", END)

    cp = checkpointer if checkpointer is not None else MemorySaver()
    return builder.compile(checkpointer=cp)
