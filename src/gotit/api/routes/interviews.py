"""REST routes for scheduled real-world interviews (companion-os P3d)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from gotit.api.auth import require_api_key
from gotit.api.routes._common import _user_id
from gotit.api.settings import Settings, get_settings
from gotit.core.models import (
    DueInterviewReminder,
    InterviewEventView,
    InterviewRampNudge,
    InterviewRampPrefs,
    InterviewStatus,
    InterviewUpcoming,
)
from gotit.db import ops as day_ops
from gotit.db import session_scope

router = APIRouter()


class InterviewIn(BaseModel):
    id: UUID | None = None
    company: str = Field(min_length=1, max_length=200)
    role_title: str = Field(min_length=1, max_length=200)
    scheduled_at: datetime
    round: str | None = Field(default=None, max_length=32)
    status: InterviewStatus = InterviewStatus.SCHEDULED
    notes: str | None = None
    remind_offsets_hours: list[int] | None = None


class InterviewPatch(BaseModel):
    company: str | None = Field(default=None, min_length=1, max_length=200)
    role_title: str | None = Field(default=None, min_length=1, max_length=200)
    scheduled_at: datetime | None = None
    round: str | None = Field(default=None, max_length=32)
    status: InterviewStatus | None = None
    notes: str | None = None
    remind_offsets_hours: list[int] | None = None


class InterviewStatusIn(BaseModel):
    status: InterviewStatus


class RemindedIn(BaseModel):
    at: datetime | None = None


@router.get(
    "/v1/interviews",
    response_model=list[InterviewEventView],
    dependencies=[Depends(require_api_key)],
)
async def list_interviews(
    settings: Annotated[Settings, Depends(get_settings)],
    include_done: bool = False,
) -> list[InterviewEventView]:
    async with session_scope() as session:
        return await day_ops.list_interviews(
            session, user_id=_user_id(settings), include_done=include_done
        )


@router.post(
    "/v1/interviews",
    response_model=InterviewEventView,
    dependencies=[Depends(require_api_key)],
)
async def upsert_interview(
    body: InterviewIn,
    settings: Annotated[Settings, Depends(get_settings)],
) -> InterviewEventView:
    async with session_scope() as session:
        view = await day_ops.upsert_interview(
            session,
            interview_id=body.id,
            company=body.company,
            role_title=body.role_title,
            scheduled_at=body.scheduled_at,
            round=body.round,
            status=body.status,
            notes=body.notes,
            remind_offsets_hours=body.remind_offsets_hours,
            user_id=_user_id(settings),
        )
    from gotit.bridge.calendar import sync_interview_to_calendar

    sync_interview_to_calendar(view)
    return view


@router.get(
    "/v1/interviews/due-reminders",
    response_model=list[DueInterviewReminder],
    dependencies=[Depends(require_api_key)],
)
async def list_due_interview_reminders(
    settings: Annotated[Settings, Depends(get_settings)],
    now: Annotated[datetime | None, Query()] = None,
) -> list[DueInterviewReminder]:
    at = now or datetime.now(UTC)
    async with session_scope() as session:
        return await day_ops.list_due_interview_reminders(
            session, at, user_id=_user_id(settings)
        )


@router.get(
    "/v1/interviews/upcoming",
    response_model=list[InterviewUpcoming],
    dependencies=[Depends(require_api_key)],
)
async def list_upcoming_interviews(
    settings: Annotated[Settings, Depends(get_settings)],
    now: Annotated[datetime | None, Query()] = None,
) -> list[InterviewUpcoming]:
    at = now or datetime.now(UTC)
    async with session_scope() as session:
        return await day_ops.list_upcoming_interviews(
            session, at, user_id=_user_id(settings)
        )


@router.get(
    "/v1/interviews/ramp-nudges",
    response_model=list[InterviewRampNudge],
    dependencies=[Depends(require_api_key)],
)
async def list_interview_ramp_nudges(
    settings: Annotated[Settings, Depends(get_settings)],
    now: Annotated[datetime | None, Query()] = None,
) -> list[InterviewRampNudge]:
    at = now or datetime.now(UTC)
    async with session_scope() as session:
        return await day_ops.list_interview_ramp_nudges(
            session, at, user_id=_user_id(settings)
        )


@router.get(
    "/v1/interviews/ramp-prefs",
    response_model=InterviewRampPrefs,
    dependencies=[Depends(require_api_key)],
)
async def get_interview_ramp_prefs(
    settings: Annotated[Settings, Depends(get_settings)],
) -> InterviewRampPrefs:
    async with session_scope() as session:
        return await day_ops.get_interview_ramp_prefs(
            session, user_id=_user_id(settings)
        )


@router.put(
    "/v1/interviews/ramp-prefs",
    response_model=InterviewRampPrefs,
    dependencies=[Depends(require_api_key)],
)
async def put_interview_ramp_prefs(
    body: InterviewRampPrefs,
    settings: Annotated[Settings, Depends(get_settings)],
) -> InterviewRampPrefs:
    async with session_scope() as session:
        return await day_ops.put_interview_ramp_prefs(
            session, body, user_id=_user_id(settings)
        )


@router.patch(
    "/v1/interviews/{interview_id}",
    response_model=InterviewEventView,
    dependencies=[Depends(require_api_key)],
)
async def patch_interview(
    interview_id: UUID,
    body: InterviewPatch,
    settings: Annotated[Settings, Depends(get_settings)],
) -> InterviewEventView:
    fields = body.model_dump(exclude_unset=True)
    async with session_scope() as session:
        try:
            view = await day_ops.patch_interview(
                session, interview_id, user_id=_user_id(settings), **fields
            )
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    from gotit.bridge.calendar import sync_interview_to_calendar

    sync_interview_to_calendar(view)
    return view


@router.delete(
    "/v1/interviews/{interview_id}",
    dependencies=[Depends(require_api_key)],
)
async def delete_interview(
    interview_id: UUID,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    async with session_scope() as session:
        try:
            await day_ops.delete_interview(
                session, interview_id, user_id=_user_id(settings)
            )
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    from gotit.bridge.calendar import rm_interview

    rm_interview(interview_id)
    return {"status": "deleted"}


@router.post(
    "/v1/interviews/{interview_id}/reminded",
    response_model=InterviewEventView,
    dependencies=[Depends(require_api_key)],
)
async def mark_interview_reminded(
    interview_id: UUID,
    settings: Annotated[Settings, Depends(get_settings)],
    body: RemindedIn | None = None,
) -> InterviewEventView:
    at = body.at if body else None
    async with session_scope() as session:
        try:
            return await day_ops.mark_interview_reminded(
                session, interview_id, at=at, user_id=_user_id(settings)
            )
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/v1/interviews/{interview_id}/ramp-nudged",
    response_model=InterviewEventView,
    dependencies=[Depends(require_api_key)],
)
async def mark_interview_ramp_nudged(
    interview_id: UUID,
    settings: Annotated[Settings, Depends(get_settings)],
    body: RemindedIn | None = None,
) -> InterviewEventView:
    at = body.at if body else None
    async with session_scope() as session:
        try:
            return await day_ops.mark_interview_ramp_nudged(
                session, interview_id, at=at, user_id=_user_id(settings)
            )
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
