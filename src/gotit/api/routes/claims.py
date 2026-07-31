"""Claim dependency (depends_on) minimal API."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from gotit.api.auth import require_api_key
from gotit.api.routes._common import _user_id
from gotit.api.settings import Settings, get_settings
from gotit.db import ops as day_ops
from gotit.db import session_scope

router = APIRouter()


class AddDependsBody(BaseModel):
    prereq_claim_id: UUID = Field(
        description="Prerequisite claim that must be mastered first."
    )


class DependsEdgeOut(BaseModel):
    claim_id: UUID
    prereq_claim_id: UUID
    rel: str = "depends_on"


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
