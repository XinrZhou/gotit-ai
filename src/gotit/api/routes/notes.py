"""Note CRUD, note ingest (Compass), and claim curation."""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from gotit.api.auth import require_api_key
from gotit.api.deps import SessionMemoryReader, SessionPromptReader, get_model
from gotit.api.routes._common import _user_id
from gotit.api.settings import Settings, get_settings
from gotit.core.agents.compass import build_compass_agent, run_compass
from gotit.core.models import Claim, DayNoteView, DayPlanView, MasteryStatus
from gotit.db import ops as day_ops
from gotit.db import session_scope
from gotit.db.models import DayNoteRow, LearningDayRow

router = APIRouter()


class NoteCreate(BaseModel):
    body: str = Field(min_length=1)
    title: str | None = None
    tags: list[str] = Field(default_factory=list)
    project_id: UUID | None = None


class NoteIngestRequest(BaseModel):
    add_plan_item: bool = True


class CurateRequest(BaseModel):
    day: date
    claim_texts: list[str] = Field(default_factory=list)


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


@router.get(
    "/v1/notes",
    response_model=list[DayNoteView],
    dependencies=[Depends(require_api_key)],
)
async def get_all_notes(
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[DayNoteView]:
    async with session_scope() as session:
        return await day_ops.list_all_notes(session, user_id=_user_id(settings))


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
            project_id=body.project_id,
        )


@router.post("/v1/notes/{note_id}/ingest", dependencies=[Depends(require_api_key)])
async def ingest_note(
    note_id: UUID,
    settings: Annotated[Settings, Depends(get_settings)],
    body: NoteIngestRequest | None = None,
) -> dict[str, object]:
    payload = body or NoteIngestRequest()
    user_id = _user_id(settings)
    claims: list[Claim] | None = None

    # Use Compass when an LLM is configured; otherwise fall back to stub extraction.
    if settings.llm_api_key:
        async with session_scope() as session:
            note = await session.get(DayNoteRow, note_id)
            if note is None or (
                await session.get(LearningDayRow, note.day_id) is None
            ):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"note not found: {note_id}",
                )
            prompt = await SessionPromptReader(session).get_active_prompt("compass")
            system_prompt = prompt.system_prompt if prompt else ""
            reader = SessionMemoryReader(session, user_id=user_id)
            agent = build_compass_agent(get_model(), system_prompt=system_prompt)
            note_plain = day_ops._strip_html(note.body)
            output = await run_compass(agent, reader, note_body=note_plain)
        claims = [
            Claim(
                text=c.text,
                source_excerpt=note_plain[:200],
                status=MasteryStatus.NOT_YET,
                source_note_id=note_id,
                topic=c.topic,
                tags=list(c.tags),
            )
            for c in output.claims
        ]

    try:
        async with session_scope() as session:
            return await day_ops.ingest_note(
                session,
                note_id,
                claims=claims,
                user_id=user_id,
                add_plan_item=payload.add_plan_item,
            )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/v1/curate",
    response_model=DayPlanView,
    dependencies=[Depends(require_api_key)],
)
async def curate(
    body: CurateRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DayPlanView:
    try:
        async with session_scope() as session:
            return await day_ops.curate_claims(
                session,
                body.day,
                claim_texts=body.claim_texts,
                user_id=_user_id(settings),
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
