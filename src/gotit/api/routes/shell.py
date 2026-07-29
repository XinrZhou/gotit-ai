"""OpenClaw shell writeback + observation endpoints."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from gotit.api.auth import require_api_key
from gotit.api.routes._common import _user_id
from gotit.api.settings import Settings, get_settings
from gotit.core.models import GraphView, MemoryEntry, ProfileView
from gotit.db import ops as day_ops
from gotit.db import session_scope

router = APIRouter()


class ShellEventCreate(BaseModel):
    job: str = Field(min_length=1, max_length=64)
    items: list[dict[str, Any]] = Field(default_factory=list)
    due_summary: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    delivery_ok: bool | None = None
    channel: str = "openclaw-weixin"
    skill: str = "digest"
    run_id: str | None = None


class InterestCreate(BaseModel):
    event_id: UUID
    item_index: int = Field(ge=1, le=50)
    title: str = Field(min_length=1, max_length=500)
    link: str | None = None
    feed_id: str | None = None
    topic: str | None = None
    channel: str = "openclaw-weixin"
    skill: str = "digest"


@router.post(
    "/v1/shell/events",
    response_model=MemoryEntry,
    dependencies=[Depends(require_api_key)],
)
async def create_shell_event(
    body: ShellEventCreate,
    settings: Annotated[Settings, Depends(get_settings)],
) -> MemoryEntry:
    async with session_scope() as session:
        return await day_ops.record_shell_event(
            session,
            user_id=_user_id(settings),
            job=body.job,
            items=body.items,
            due_summary=body.due_summary,
            errors=body.errors,
            delivery_ok=body.delivery_ok,
            channel=body.channel,
            skill=body.skill,
            run_id=body.run_id,
        )


@router.post(
    "/v1/shell/interest",
    response_model=MemoryEntry,
    dependencies=[Depends(require_api_key)],
)
async def create_interest(
    body: InterestCreate,
    settings: Annotated[Settings, Depends(get_settings)],
) -> MemoryEntry:
    async with session_scope() as session:
        return await day_ops.record_interest(
            session,
            user_id=_user_id(settings),
            event_id=body.event_id,
            item_index=body.item_index,
            title=body.title,
            link=body.link,
            feed_id=body.feed_id,
            topic=body.topic,
            channel=body.channel,
            skill=body.skill,
        )


@router.get(
    "/v1/shell/activity",
    response_model=list[MemoryEntry],
    dependencies=[Depends(require_api_key)],
)
async def shell_activity(
    settings: Annotated[Settings, Depends(get_settings)],
    kinds: Annotated[str | None, Query(description="Comma: shell_event,interest")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[MemoryEntry]:
    kind_list = [k.strip() for k in kinds.split(",")] if kinds else None
    if kind_list is not None:
        kind_list = [k for k in kind_list if k]
        if not kind_list:
            raise HTTPException(status_code=400, detail="kinds empty")
    async with session_scope() as session:
        return await day_ops.list_shell_activity(
            session,
            user_id=_user_id(settings),
            kinds=kind_list,
            limit=limit,
        )


@router.get(
    "/v1/obs/profile",
    response_model=ProfileView,
    dependencies=[Depends(require_api_key)],
)
async def obs_profile(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ProfileView:
    async with session_scope() as session:
        return await day_ops.build_profile_v0(session, user_id=_user_id(settings))


@router.get(
    "/v1/obs/graph",
    response_model=GraphView,
    dependencies=[Depends(require_api_key)],
)
async def obs_graph(
    settings: Annotated[Settings, Depends(get_settings)],
) -> GraphView:
    async with session_scope() as session:
        return await day_ops.build_graph_v0(session, user_id=_user_id(settings))
