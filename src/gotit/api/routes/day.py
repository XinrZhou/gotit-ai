"""Day, plan, and plan-item chat-message endpoints."""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from gotit.api.auth import require_api_key
from gotit.api.routes._common import _user_id
from gotit.api.settings import Settings, get_settings
from gotit.core.models import (
    ChatMessageView,
    DayPlanView,
    PlanItemSource,
    PlanItemStatus,
    PlanItemView,
    TodayView,
)
from gotit.db import ops as day_ops
from gotit.db import session_scope

router = APIRouter()


class PlanItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    item_id: UUID | None = None
    source: PlanItemSource = PlanItemSource.MANUAL
    status: PlanItemStatus = PlanItemStatus.PLANNED
    claim_id: UUID | None = None
    sort_order: int | None = None
    due_at: date | None = None
    due_time: str | None = Field(
        default=None, description="HH:MM local wall clock for Reminders"
    )


class PlanItemPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    status: PlanItemStatus | None = None
    sort_order: int | None = None
    due_at: date | None = None
    due_time: str | None = None
    defer_to: date | None = None


class ChatMessageCreate(BaseModel):
    role: str = Field(min_length=1, max_length=16)
    text: str = Field(min_length=1)


@router.get("/v1/today", response_model=TodayView, dependencies=[Depends(require_api_key)])
async def today(
    settings: Annotated[Settings, Depends(get_settings)],
    day: Annotated[date | None, Query()] = None,
) -> TodayView:
    async with session_scope() as session:
        return await day_ops.get_today(session, day, user_id=_user_id(settings))


@router.get(
    "/v1/days/{day}/plan",
    response_model=DayPlanView,
    dependencies=[Depends(require_api_key)],
)
async def get_plan(
    day: date,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DayPlanView:
    async with session_scope() as session:
        return await day_ops.get_plan(session, day, user_id=_user_id(settings))


@router.post(
    "/v1/days/{day}/plan/items",
    response_model=PlanItemView,
    dependencies=[Depends(require_api_key)],
)
async def create_plan_item(
    day: date,
    body: PlanItemCreate,
    settings: Annotated[Settings, Depends(get_settings)],
) -> PlanItemView:
    async with session_scope() as session:
        try:
            view = await day_ops.upsert_plan_item(
                session,
                day,
                title=body.title,
                user_id=_user_id(settings),
                item_id=body.item_id,
                source=body.source,
                status=body.status,
                claim_id=body.claim_id,
                sort_order=body.sort_order,
                due_at=body.due_at,
                due_time=body.due_time,
            )
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    from gotit.bridge.reminders import push_day

    push_day(day, title=view.title, time=view.due_time, reconcile=True)
    return view


@router.post(
    "/v1/days/{day}/plan/fill-queue",
    response_model=DayPlanView,
    dependencies=[Depends(require_api_key)],
)
async def fill_plan_from_queue(
    day: date,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DayPlanView:
    async with session_scope() as session:
        return await day_ops.fill_today_from_queue(session, day, user_id=_user_id(settings))


@router.patch(
    "/v1/plan/items/{item_id}",
    response_model=PlanItemView,
    dependencies=[Depends(require_api_key)],
)
async def patch_plan_item(
    item_id: UUID,
    body: PlanItemPatch,
    settings: Annotated[Settings, Depends(get_settings)],
) -> PlanItemView:
    async with session_scope() as session:
        try:
            view = await day_ops.update_plan_item(
                session,
                item_id,
                title=body.title,
                status=body.status,
                sort_order=body.sort_order,
                due_at=body.due_at,
                due_time=body.due_time,
                defer_to=body.defer_to,
                user_id=_user_id(settings),
            )
            # Resolve calendar day after possible defer.
            plan_day = body.defer_to
            if plan_day is None:
                from gotit.db.models import LearningDayRow, PlanItemRow

                row = await session.get(PlanItemRow, item_id)
                if row is not None:
                    day_row = await session.get(LearningDayRow, row.day_id)
                    if day_row is not None:
                        plan_day = day_row.day
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if plan_day is not None:
        from gotit.bridge.reminders import push_day

        push_day(plan_day, reconcile=True)
    return view


@router.delete(
    "/v1/plan/items/{item_id}",
    dependencies=[Depends(require_api_key)],
)
async def delete_plan_item(
    item_id: UUID,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, bool]:
    title: str | None = None
    plan_day: date | None = None
    async with session_scope() as session:
        try:
            from gotit.db.models import LearningDayRow, PlanItemRow

            row = await session.get(PlanItemRow, item_id)
            if row is not None:
                title = row.title
                day_row = await session.get(LearningDayRow, row.day_id)
                if day_row is not None:
                    plan_day = day_row.day
            await day_ops.delete_plan_item(session, item_id, user_id=_user_id(settings))
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if title and plan_day is not None:
        from gotit.bridge.reminders import rm_item

        rm_item(plan_day, title)
    return {"ok": True}


@router.get(
    "/v1/plan/items/{item_id}/messages",
    response_model=list[ChatMessageView],
    dependencies=[Depends(require_api_key)],
)
async def list_messages(
    item_id: UUID,
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[ChatMessageView]:
    async with session_scope() as session:
        try:
            return await day_ops.list_chat_messages(
                session, item_id, user_id=_user_id(settings)
            )
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/v1/plan/items/{item_id}/messages",
    response_model=ChatMessageView,
    dependencies=[Depends(require_api_key)],
)
async def create_message(
    item_id: UUID,
    body: ChatMessageCreate,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ChatMessageView:
    async with session_scope() as session:
        try:
            return await day_ops.add_chat_message(
                session,
                item_id,
                body.role,
                body.text,
                user_id=_user_id(settings),
            )
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
