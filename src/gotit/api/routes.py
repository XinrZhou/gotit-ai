from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from gotit import __version__
from gotit.api.auth import require_api_key
from gotit.api.settings import Settings, get_settings
from gotit.core.models import (
    CheckMode,
    ChatMessageView,
    Claim,
    DayNoteView,
    DayPlanView,
    LoopState,
    PlanItemSource,
    PlanItemStatus,
    PlanItemView,
    TodayView,
)
from gotit.db import ops as day_ops
from gotit.db import session_scope
from gotit.db.models import ChatMessageRow, ClaimRow

router = APIRouter()


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str


class IngestRequest(BaseModel):
    material: str = Field(min_length=1, description="Raw study material to extract claims from")


class IngestResponse(BaseModel):
    claims: list[Claim]
    state: LoopState
    note: str = "stub: claim extraction not wired yet"


class ExamineRequest(BaseModel):
    claim_id: UUID
    mode: CheckMode = CheckMode.PROBE
    passed: bool | None = Field(
        default=None,
        description="Stub writeback flag until Examiner is wired; True/False updates plan+claim",
    )


class PlanItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    item_id: UUID | None = None
    source: PlanItemSource = PlanItemSource.MANUAL
    status: PlanItemStatus = PlanItemStatus.PLANNED
    claim_id: UUID | None = None
    sort_order: int | None = None
    due_at: date | None = None


class PlanItemPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    status: PlanItemStatus | None = None
    sort_order: int | None = None
    due_at: date | None = None
    defer_to: date | None = None


class NoteCreate(BaseModel):
    body: str = Field(min_length=1)
    title: str | None = None
    tags: list[str] = Field(default_factory=list)


class NoteIngestRequest(BaseModel):
    add_plan_item: bool = True


def _user_id(settings: Settings) -> str:
    return settings.gotit_user_id


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(version=__version__)


@router.post("/v1/ingest", response_model=IngestResponse, dependencies=[Depends(require_api_key)])
async def ingest(
    body: IngestRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> IngestResponse:
    claim = day_ops.stub_extract_claim(body.material)
    async with session_scope() as session:
        from gotit.db.models import ClaimRow

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


@router.post("/v1/examine", dependencies=[Depends(require_api_key)])
async def examine(
    body: ExamineRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    result: dict[str, object] = {
        "claim_id": str(body.claim_id),
        "mode": body.mode,
        "status": "stub",
        "message": "Examiner not wired yet",
    }
    if body.passed is not None:
        try:
            async with session_scope() as session:
                writeback = await day_ops.apply_examine_result(
                    session,
                    body.claim_id,
                    passed=body.passed,
                    user_id=_user_id(settings),
                )
            result["writeback"] = writeback
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return result


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
            return await day_ops.upsert_plan_item(
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
            )
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


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
            return await day_ops.update_plan_item(
                session,
                item_id,
                title=body.title,
                status=body.status,
                sort_order=body.sort_order,
                due_at=body.due_at,
                defer_to=body.defer_to,
                user_id=_user_id(settings),
            )
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete(
    "/v1/plan/items/{item_id}",
    dependencies=[Depends(require_api_key)],
)
async def delete_plan_item(
    item_id: UUID,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, bool]:
    async with session_scope() as session:
        try:
            await day_ops.delete_plan_item(session, item_id, user_id=_user_id(settings))
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"ok": True}


class ChatMessageCreate(BaseModel):
    role: str = Field(min_length=1, max_length=16)
    text: str = Field(min_length=1)


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


@router.get(
    "/v1/days/{day}/notes",
    response_model=list[DayNoteView],
    dependencies=[Depends(require_api_key)],
)
async def get_notes(
    day: date,
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[DayNoteView]:
    async with session_scope() as session:
        return await day_ops.list_notes(session, day, user_id=_user_id(settings), full_body=False)


@router.post(
    "/v1/days/{day}/notes",
    response_model=DayNoteView,
    dependencies=[Depends(require_api_key)],
)
async def create_note(
    day: date,
    body: NoteCreate,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DayNoteView:
    async with session_scope() as session:
        return await day_ops.add_note(
            session,
            day,
            body.body,
            title=body.title,
            tags=body.tags,
            user_id=_user_id(settings),
        )


@router.post("/v1/notes/{note_id}/ingest", dependencies=[Depends(require_api_key)])
async def ingest_note(
    note_id: UUID,
    settings: Annotated[Settings, Depends(get_settings)],
    body: NoteIngestRequest | None = None,
) -> dict[str, object]:
    payload = body or NoteIngestRequest()
    async with session_scope() as session:
        try:
            return await day_ops.ingest_note(
                session,
                note_id,
                user_id=_user_id(settings),
                add_plan_item=payload.add_plan_item,
            )
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/v1/notes/{note_id}",
    response_model=DayNoteView,
    dependencies=[Depends(require_api_key)],
)
async def get_note(
    note_id: UUID,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DayNoteView:
    async with session_scope() as session:
        try:
            return await day_ops.get_note(session, note_id, user_id=_user_id(settings))
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete(
    "/v1/notes/{note_id}",
    dependencies=[Depends(require_api_key)],
)
async def delete_note(
    note_id: UUID,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, bool]:
    async with session_scope() as session:
        try:
            await day_ops.delete_note(session, note_id, user_id=_user_id(settings))
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"ok": True}
