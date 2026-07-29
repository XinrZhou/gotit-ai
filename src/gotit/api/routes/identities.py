"""Agent identity management — seed and observe persistent personalities."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from gotit.api.auth import require_api_key
from gotit.api.settings import Settings, get_settings
from gotit.core.models import AgentIdentity
from gotit.db import ops as day_ops
from gotit.db import session_scope

router = APIRouter()


@router.post(
    "/v1/identities/seed",
    response_model=list[AgentIdentity],
    dependencies=[Depends(require_api_key)],
)
async def seed_identities(
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[AgentIdentity]:
    """Idempotently seed the 5 default agent identities, pinning active rubrics."""
    async with session_scope() as session:
        return await day_ops.seed_default_identities(session)


@router.get(
    "/v1/identities",
    response_model=list[AgentIdentity],
    dependencies=[Depends(require_api_key)],
)
async def list_identities(
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[AgentIdentity]:
    async with session_scope() as session:
        return await day_ops.list_identities(session)

