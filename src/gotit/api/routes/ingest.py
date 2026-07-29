"""Material ingest (stub claim extraction)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from gotit.api.auth import require_api_key
from gotit.api.routes._common import _user_id
from gotit.api.settings import Settings, get_settings
from gotit.core.models import Claim, LoopState
from gotit.db import session_scope
from gotit.db.models import ClaimRow

router = APIRouter()


class IngestRequest(BaseModel):
    material: str = Field(min_length=1, description="Raw study material to extract claims from")


class IngestResponse(BaseModel):
    claims: list[Claim]
    state: LoopState
    note: str = "stub: claim extraction not wired yet"


@router.post("/v1/ingest", response_model=IngestResponse, dependencies=[Depends(require_api_key)])
async def ingest(
    body: IngestRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> IngestResponse:
    from gotit.db import ops as day_ops

    claim = day_ops.stub_extract_claim(body.material)
    async with session_scope() as session:
        session.add(
            ClaimRow(
                id=claim.id,
                user_id=_user_id(settings),
                text=claim.text,
                source_excerpt=claim.source_excerpt,
                status=claim.status.value,
                source_note_id=None,
                next_review_at=None,
            )
        )
    return IngestResponse(claims=[claim], state=LoopState.CLAIM)
