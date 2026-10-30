"""MRV and Impact Verification REST routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends

from stubbleos.api.auth import AuthenticatedUser, get_current_user
from stubbleos.api.schemas import MrvProofResponse
from stubbleos.core.types import ImpactRecordStatus

router = APIRouter(prefix="/mrv", tags=["MRV"])

MOCK_MRV: dict[UUID, MrvProofResponse] = {}


def _seed_mock_mrv() -> None:
    if MOCK_MRV:
        return
    fld_id = UUID("00000000-0000-0000-0000-000000000001")
    rec_id = UUID("00000000-0000-0000-0006-000000000001")
    MOCK_MRV[fld_id] = MrvProofResponse(
        id=rec_id,
        field_id=fld_id,
        season="Kharif-2026",
        co2e_avoided_tonnes=7.2,
        baseline_burned_prob=0.88,
        bundle_sha256="4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a",
        verified_status=ImpactRecordStatus.INDICATIVE,
        impact_label="indicative impact record (not registry-verified)",
    )


_seed_mock_mrv()


@router.get("/{field_id}", response_model=MrvProofResponse)
def get_field_mrv_proof(
    field_id: UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)] = None,  # type: ignore[assignment]
) -> MrvProofResponse:
    _seed_mock_mrv()
    if field_id in MOCK_MRV:
        return MOCK_MRV[field_id]

    # Generate synthetic proof on the fly for demo fields
    rec_id = uuid4()
    proof = MrvProofResponse(
        id=rec_id,
        field_id=field_id,
        season="Kharif-2026",
        co2e_avoided_tonnes=5.4,
        baseline_burned_prob=0.82,
        bundle_sha256="c2a550c609c11860d5e16fd9b1bc48d9aa178875883651c6819207c4bc5f1599",
        verified_status=ImpactRecordStatus.INDICATIVE,
        impact_label="indicative impact record (not registry-verified)",
    )
    MOCK_MRV[field_id] = proof
    return proof
