"""Memory observation endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from gotit.api.auth import require_api_key
from gotit.api.routes._common import _user_id
from gotit.api.settings import Settings, get_settings
from gotit.core.models import MemoryEntry
from gotit.db import ops as day_ops
from gotit.db import session_scope

router = APIRouter()


class MemoryCreate(BaseModel):
    layer: str = Field(min_length=1, max_length=16)
    kind: str = Field(min_length=1, max_length=64)
    content: dict[str, object] = Field(default_factory=dict)
    topic: str | None = None
    source: dict[str, object] | None = None
    expires_at: datetime | None = None


@router.get(
    "/v1/memory",
    response_model=list[MemoryEntry],
    dependencies=[Depends(require_api_key)],
)
async def list_memory(
    settings: Annotated[Settings, Depends(get_settings)],
    layer: Annotated[str | None, Query()] = None,
    kind: Annotated[str | None, Query()] = None,
    topic: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[MemoryEntry]:
    async with session_scope() as session:
        return await day_ops.list_memory(
            session,
            user_id=_user_id(settings),
            layer=layer,
            kind=kind,
            topic=topic,
            limit=limit,
        )


@router.get(
    "/v1/memory/failure-digests/pending",
    response_model=list[MemoryEntry],
    dependencies=[Depends(require_api_key)],
)
async def list_pending_failure_digests(
    settings: Annotated[Settings, Depends(get_settings)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[MemoryEntry]:
    async with session_scope() as session:
        return await day_ops.list_pending_failure_digests(
            session, user_id=_user_id(settings), limit=limit
        )


@router.post(
    "/v1/memory/failure-digests/{memory_id}/notified",
    response_model=MemoryEntry,
    dependencies=[Depends(require_api_key)],
)
async def mark_failure_digest_notified(
    memory_id: UUID,
    settings: Annotated[Settings, Depends(get_settings)],
) -> MemoryEntry:
    try:
        async with session_scope() as session:
            return await day_ops.mark_failure_digest_notified(
                session, memory_id, user_id=_user_id(settings)
            )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.post(
    "/v1/memory",
    response_model=MemoryEntry,
    dependencies=[Depends(require_api_key)],
)
async def create_memory(
    body: MemoryCreate,
    settings: Annotated[Settings, Depends(get_settings)],
) -> MemoryEntry:
    async with session_scope() as session:
        entry = await day_ops.add_memory(
            session,
            user_id=_user_id(settings),
            layer=body.layer,
            kind=body.kind,
            content=body.content,
            topic=body.topic,
            source=body.source,
            expires_at=body.expires_at,
        )
    return entry
