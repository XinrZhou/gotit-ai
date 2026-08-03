"""Claim dependency (depends_on) + preferred check mode API."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from gotit.api.auth import require_api_key
from gotit.api.routes._common import _user_id
from gotit.api.settings import Settings, get_settings
from gotit.core.models import Claim
from gotit.db import ops as day_ops
from gotit.db import session_scope

router = APIRouter()

PreferredModeIn = Literal["probe", "drill", "teach_back"] | None


class AddDependsBody(BaseModel):
    prereq_claim_id: UUID = Field(
        description="Prerequisite claim that must be mastered first."
    )


class ClaimPreferredModeBody(BaseModel):
    preferred_check_mode: PreferredModeIn = Field(
        default=None,
        description="Verify form preference; null clears to default probe.",
    )


class DependsEdgeOut(BaseModel):
    claim_id: UUID
    prereq_claim_id: UUID
    rel: str = "depends_on"


@router.patch(
    "/v1/claims/{claim_id}",
    response_model=Claim,
    dependencies=[Depends(require_api_key)],
)
async def patch_claim(
    claim_id: UUID,
    body: ClaimPreferredModeBody,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Claim:
    try:
        async with session_scope() as session:
            return await day_ops.set_claim_preferred_check_mode(
                session,
                claim_id,
                preferred_check_mode=body.preferred_check_mode,
                user_id=_user_id(settings),
            )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/v1/claims/{claim_id}/depends-on",
    response_model=list[DependsEdgeOut],
    dependencies=[Depends(require_api_key)],
)
async def list_claim_depends(
    claim_id: UUID,
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[DependsEdgeOut]:
    async with session_scope() as session:
        rows = await day_ops.list_depends_edges(
            session, user_id=_user_id(settings), claim_id=claim_id
        )
    return [
        DependsEdgeOut(
            claim_id=r.source_claim_id,
            prereq_claim_id=r.target_claim_id,
        )
        for r in rows
    ]


@router.post(
    "/v1/claims/{claim_id}/depends-on",
    response_model=DependsEdgeOut,
    dependencies=[Depends(require_api_key)],
)
async def add_claim_depends(
    claim_id: UUID,
    body: AddDependsBody,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DependsEdgeOut:
    try:
        async with session_scope() as session:
            row = await day_ops.add_depends_on(
                session,
                user_id=_user_id(settings),
                claim_id=claim_id,
                prereq_claim_id=body.prereq_claim_id,
            )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DependsEdgeOut(
        claim_id=row.source_claim_id,
        prereq_claim_id=row.target_claim_id,
    )


@router.delete(
    "/v1/claims/{claim_id}/depends-on/{prereq_claim_id}",
    dependencies=[Depends(require_api_key)],
)
async def delete_claim_depends(
    claim_id: UUID,
    prereq_claim_id: UUID,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    async with session_scope() as session:
        removed = await day_ops.remove_depends_on(
            session,
            user_id=_user_id(settings),
            claim_id=claim_id,
            prereq_claim_id=prereq_claim_id,
        )
    if not removed:
        raise HTTPException(status_code=404, detail="depends_on edge not found")
    return {"ok": True, "removed": True}
