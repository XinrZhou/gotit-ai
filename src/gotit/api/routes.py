from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from gotit import __version__
from gotit.api.auth import require_api_key
from gotit.api.deps import SessionMemoryReader, SessionPromptReader, get_model
from gotit.api.settings import Settings, get_settings
from gotit.core.agents.axiom import (
    build_axiom_agent,
    build_topic_axiom_agent,
    run_axiom,
    run_topic_examine,
    stub_topic_examine,
)
from gotit.core.agents.compass import build_compass_agent, run_compass
from gotit.core.agents.echo import build_echo_agent, run_echo
from gotit.core.agents.sage import build_sage_agent, run_sage, stub_sage
from gotit.core.models import (
    ChatMessageView,
    Claim,
    DayNoteView,
    DayPlanView,
    DrillMaterial,
    DrillRound,
    DrillSession,
    LoopState,
    MasteryStatus,
    MemoryEntry,
    PlanItemSource,
    PlanItemStatus,
    PlanItemView,
    Project,
    ProjectProgress,
    ProjectStatus,
    PromptVersion,
    ResumeDocument,
    ResumeRecord,
    SageVerdict,
    TeachVerdict,
    TodayView,
)
from gotit.core.resume.extract import ResumeExtractError, extract_text
from gotit.core.resume.parse import build_resume_parser, run_resume_parser, stub_parse
from gotit.db import ops as day_ops
from gotit.db import session_scope
from gotit.db.models import ClaimRow, DayNoteRow, LearningDayRow
from gotit.prompts import load_prompt_dir

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
    claim_id: UUID | None = Field(
        default=None,
        description="Single-claim mode target; used when topic/note_id absent.",
    )
    topic: str | None = Field(
        default=None,
        description="Topic-session mode: Axiom shuttles across the topic's claims.",
    )
    note_id: UUID | None = Field(
        default=None,
        description="Note-session mode: Axiom shuttles across the note's claims.",
    )
    answer: str | None = Field(
        default=None,
        description="Learner's latest answer; omit on the first turn.",
    )
    history: list[dict[str, str]] = Field(
        default_factory=list,
        description="Prior turns [{role: examiner|user, text}].",
    )
    verdict: str | None = Field(
        default=None,
        description=(
            "Direct verdict (passed|almost|owe_next) bypassing the agent; "
            "used for stubs/tests (single-claim mode only)."
        ),
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
    project_id: UUID | None = None


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
    user_id = _user_id(settings)

    # --- Claims-session modes (note_id or topic): Axiom shuttles across claims ---
    if body.note_id is not None or body.topic is not None:
        async with session_scope() as session:
            if body.note_id is not None:
                claims = await day_ops.list_note_claims(
                    session, body.note_id, user_id=user_id
                )
            elif body.topic is not None:
                claims = await day_ops.list_topic_claims_today(
                    session, body.topic, user_id=user_id
                )
        if not settings.llm_api_key:
            session_verdict = stub_topic_examine(
                claims=claims, answer=body.answer, history=body.history
            )
        else:
            async with session_scope() as session:
                prompt = await SessionPromptReader(session).get_active_prompt("axiom")
                system_prompt = prompt.system_prompt if prompt else ""
                reader = SessionMemoryReader(session, user_id=user_id)
                claims_agent = build_topic_axiom_agent(
                    get_model(), system_prompt=system_prompt
                )
            session_verdict = await run_topic_examine(
                claims_agent,
                reader,
                topic=body.topic or "",
                claims=claims,
                history=body.history,
                answer=body.answer,
            )
        writeback: dict[str, object] | None = None
        if (
            session_verdict.done
            and session_verdict.verdict is not None
            and session_verdict.current_claim_id
        ):
            try:
                async with session_scope() as session:
                    writeback = await day_ops.apply_examine_verdict(
                        session,
                        session_verdict.current_claim_id,
                        verdict=session_verdict.verdict,
                        user_id=user_id,
                    )
            except KeyError as exc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
                ) from exc
        return {
            "verdict": session_verdict.model_dump(mode="json"),
            "writeback": writeback,
        }

    # --- Single-claim mode (legacy) ---
    if body.claim_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="one of `note_id`, `topic`, or `claim_id` is required",
        )

    # Direct-verdict path: bypass the agent (stub / tests / manual override).
    if body.verdict is not None:
        try:
            async with session_scope() as session:
                direct_writeback = await day_ops.apply_examine_verdict(
                    session,
                    body.claim_id,
                    verdict=body.verdict,
                    user_id=user_id,
                )
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        return {
            "verdict": {
                "done": True,
                "verdict": body.verdict,
                "score": None,
                "evidence": None,
                "follow_up": "",
            },
            "writeback": direct_writeback,
        }

    # Agent path: multi-turn examination.
    try:
        async with session_scope() as session:
            claim = await session.get(ClaimRow, body.claim_id)
            if claim is None or claim.user_id != user_id:
                raise KeyError(f"claim not found: {body.claim_id}")
            prompt = await SessionPromptReader(session).get_active_prompt("axiom")
            system_prompt = prompt.system_prompt if prompt else ""
            reader = SessionMemoryReader(session, user_id=user_id)
            agent = build_axiom_agent(get_model(), system_prompt=system_prompt)
            verdict = await run_axiom(
                agent,
                reader,
                claim_text=claim.text,
                history=body.history,
                answer=body.answer,
            )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    writeback = None
    if verdict.done and verdict.verdict is not None:
        try:
            async with session_scope() as session:
                writeback = await day_ops.apply_examine_verdict(
                    session,
                    body.claim_id,
                    verdict=verdict.verdict,
                    user_id=user_id,
                )
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return {"verdict": verdict.model_dump(mode="json"), "writeback": writeback}


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


class CurateRequest(BaseModel):
    day: date
    claim_texts: list[str] = Field(default_factory=list)


class TeachRequest(BaseModel):
    topic: str = Field(min_length=1)
    answer: str | None = Field(
        default=None,
        description="Learner's latest teaching turn; omit on the first turn.",
    )
    history: list[dict[str, str]] = Field(default_factory=list)
    you_taught_well: bool | None = Field(
        default=None,
        description="Direct verdict bypassing the agent (stub/tests).",
    )


@router.post("/v1/teach", dependencies=[Depends(require_api_key)])
async def teach(
    body: TeachRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    user_id = _user_id(settings)

    if body.you_taught_well is not None:
        return {
            "verdict": TeachVerdict(
                done=True,
                you_taught_well=body.you_taught_well,
                gaps=[],
                next_question=None,
            ).model_dump(mode="json")
        }

    async with session_scope() as session:
        prompt = await SessionPromptReader(session).get_active_prompt("echo")
        system_prompt = prompt.system_prompt if prompt else ""
        reader = SessionMemoryReader(session, user_id=user_id)
        agent = build_echo_agent(get_model(), system_prompt=system_prompt)
        verdict = await run_echo(
            agent,
            reader,
            topic=body.topic,
            history=body.history,
            answer=body.answer,
        )
    return {"verdict": verdict.model_dump(mode="json")}


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


# --- Memory & prompt observation ---


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


@router.get(
    "/v1/prompts",
    response_model=list[PromptVersion],
    dependencies=[Depends(require_api_key)],
)
async def list_prompts(
    settings: Annotated[Settings, Depends(get_settings)],
    agent_name: Annotated[str | None, Query()] = None,
    active_only: Annotated[bool, Query()] = False,
) -> list[PromptVersion]:
    async with session_scope() as session:
        return await day_ops.list_prompts(
            session,
            agent_name=agent_name,
            active_only=active_only,
        )


@router.post(
    "/v1/prompts/register",
    response_model=list[PromptVersion],
    dependencies=[Depends(require_api_key)],
)
async def register_prompts() -> list[PromptVersion]:
    versions = load_prompt_dir(Path("prompts"))
    async with session_scope() as session:
        return await day_ops.register_prompts(session, versions)


# --- Project library (projects come from resume parse; no manual create) ---


class ProjectPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    role: str | None = None
    goal: str | None = None
    tech_stack: list[str] | None = None
    status: ProjectStatus | None = None


@router.get(
    "/v1/projects",
    response_model=list[Project],
    dependencies=[Depends(require_api_key)],
)
async def list_projects(
    settings: Annotated[Settings, Depends(get_settings)],
    include_archived: Annotated[bool, Query()] = False,
) -> list[Project]:
    async with session_scope() as session:
        return await day_ops.list_projects(
            session,
            user_id=_user_id(settings),
            include_archived=include_archived,
        )


@router.get(
    "/v1/projects/{project_id}",
    response_model=Project,
    dependencies=[Depends(require_api_key)],
)
async def get_project(
    project_id: UUID,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Project:
    async with session_scope() as session:
        try:
            return await day_ops.get_project(
                session, project_id, user_id=_user_id(settings)
            )
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch(
    "/v1/projects/{project_id}",
    response_model=Project,
    dependencies=[Depends(require_api_key)],
)
async def update_project(
    project_id: UUID,
    body: ProjectPatch,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Project:
    async with session_scope() as session:
        try:
            return await day_ops.update_project(
                session,
                project_id,
                user_id=_user_id(settings),
                name=body.name,
                role=body.role,
                goal=body.goal,
                tech_stack=body.tech_stack,
                status=body.status,
            )
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/v1/projects/{project_id}/progress",
    response_model=ProjectProgress,
    dependencies=[Depends(require_api_key)],
)
async def get_project_progress(
    project_id: UUID,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ProjectProgress:
    async with session_scope() as session:
        return await day_ops.project_progress(
            session, project_id, user_id=_user_id(settings)
        )


# --- Resume upload / parse / apply ---


ALLOWED_RESUME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
}
MAX_RESUME_BYTES = 10 * 1024 * 1024


class ResumeApplyRequest(BaseModel):
    upload_id: UUID
    document: ResumeDocument
    file_path: str
    ingest: bool = False


@router.post(
    "/v1/resumes/upload",
    dependencies=[Depends(require_api_key)],
)
async def upload_resume(
    file: Annotated[UploadFile, Field(alias="file")],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    content = await file.read()
    if len(content) > MAX_RESUME_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="resume file too large (max 10MB)",
        )
    content_type = (file.content_type or "text/plain").strip()
    if content_type not in ALLOWED_RESUME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"unsupported content type: {content_type}",
        )
    upload_id = uuid4()
    ext = _resume_ext(content_type)
    file_path = f"uploads/{upload_id}.{ext}"
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    Path(file_path).write_bytes(content)
    try:
        resume_text = extract_text(content, content_type)
    except ResumeExtractError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    if not settings.llm_api_key:
        out = stub_parse(upload_id=upload_id, resume_text=resume_text)
        return {
            "upload_id": str(upload_id),
            "file_path": file_path,
            "document": out.document.model_dump(mode="json"),
        }

    system_prompt = await _active_prompt(settings, "compass")
    agent = build_resume_parser(get_model(), system_prompt=system_prompt)
    out = await run_resume_parser(agent, upload_id=upload_id, resume_text=resume_text)
    return {
        "upload_id": str(upload_id),
        "file_path": file_path,
        "document": out.document.model_dump(mode="json"),
    }


@router.post(
    "/v1/resumes/apply",
    dependencies=[Depends(require_api_key)],
)
async def apply_resume(
    body: ResumeApplyRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    async with session_scope() as session:
        result = await day_ops.apply_resume(
            session,
            body.document,
            upload_id=body.upload_id,
            file_path=body.file_path,
            ingest=body.ingest,
            user_id=_user_id(settings),
        )
    return result


@router.get(
    "/v1/resumes",
    response_model=ResumeRecord | None,
    dependencies=[Depends(require_api_key)],
)
async def get_resume(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ResumeRecord | None:
    async with session_scope() as session:
        return await day_ops.get_resume(session, user_id=_user_id(settings))


_RESUME_MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
}


@router.get(
    "/v1/resumes/file",
    dependencies=[Depends(require_api_key)],
)
async def get_resume_file(
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    """Serve the originally uploaded resume file (pdf/docx/txt/md)."""
    async with session_scope() as session:
        record = await day_ops.get_resume(session, user_id=_user_id(settings))
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no resume")
    file_path = record.file_path
    # Fallback for legacy rows whose file_path lacked an extension: glob by upload_id.
    if not Path(file_path).exists():
        candidates = sorted(Path("uploads").glob(f"{record.upload_id}.*"))
        if candidates:
            file_path = str(candidates[0])
    if not Path(file_path).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="resume file missing on disk"
        )
    ext = Path(file_path).suffix.lstrip(".").lower()
    media_type = _RESUME_MEDIA_TYPES.get(ext, "application/octet-stream")
    return FileResponse(file_path, media_type=media_type, filename=f"resume.{ext or 'bin'}")


# --- Drill materials ---


class DrillMaterialIn(BaseModel):
    id: UUID | None = None
    title: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1)


@router.get(
    "/v1/drill/materials",
    response_model=list[DrillMaterial],
    dependencies=[Depends(require_api_key)],
)
async def list_drill_materials(
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[DrillMaterial]:
    async with session_scope() as session:
        return await day_ops.list_drill_materials(session, user_id=_user_id(settings))


@router.post(
    "/v1/drill/materials",
    response_model=DrillMaterial,
    dependencies=[Depends(require_api_key)],
)
async def upsert_drill_material(
    body: DrillMaterialIn,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DrillMaterial:
    async with session_scope() as session:
        return await day_ops.upsert_drill_material(
            session,
            material_id=body.id,
            title=body.title,
            body=body.body,
            user_id=_user_id(settings),
        )


@router.patch(
    "/v1/drill/materials/{material_id}",
    response_model=DrillMaterial,
    dependencies=[Depends(require_api_key)],
)
async def update_drill_material(
    material_id: UUID,
    body: DrillMaterialIn,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DrillMaterial:
    async with session_scope() as session:
        return await day_ops.upsert_drill_material(
            session,
            material_id=material_id,
            title=body.title,
            body=body.body,
            user_id=_user_id(settings),
        )


@router.delete(
    "/v1/drill/materials/{material_id}",
    dependencies=[Depends(require_api_key)],
)
async def delete_drill_material(
    material_id: UUID,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    async with session_scope() as session:
        try:
            await day_ops.delete_drill_material(
                session, material_id, user_id=_user_id(settings)
            )
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"status": "deleted"}


# --- Drill material file import ---


@router.post(
    "/v1/drill/materials/upload",
    dependencies=[Depends(require_api_key)],
)
async def upload_drill_material(
    file: Annotated[UploadFile, Field(alias="file")],
) -> dict[str, str]:
    """Extract text from an uploaded file and return it as a material preview.

    Does not persist; the client reviews the {title, body} and saves via the
    existing upsert endpoint. Reuses resume extraction (PDF/DOCX/TXT/MD).
    """
    content = await file.read()
    if len(content) > MAX_RESUME_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="file too large (max 10MB)",
        )
    content_type = (file.content_type or "text/plain").strip()
    if content_type not in ALLOWED_RESUME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"unsupported content type: {content_type}",
        )
    try:
        body = extract_text(content, content_type)
    except ResumeExtractError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    title = (Path(file.filename or "导入资料").stem or "导入资料").strip() or "导入资料"
    return {"title": title, "body": body}


# --- Drill sessions (resume-driven mock interview) ---


class DrillSessionStart(BaseModel):
    round: DrillRound
    direction: str | None = None
    project_id: UUID | None = None


class DrillSessionContinue(BaseModel):
    answer: str = Field(min_length=1)


@router.get(
    "/v1/drill/sessions",
    response_model=list[DrillSession],
    dependencies=[Depends(require_api_key)],
)
async def list_drill_sessions(
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[DrillSession]:
    async with session_scope() as session:
        return await day_ops.list_drill_sessions(session, user_id=_user_id(settings))


@router.get(
    "/v1/drill/sessions/{session_id}",
    response_model=DrillSession,
    dependencies=[Depends(require_api_key)],
)
async def get_drill_session(
    session_id: UUID,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DrillSession:
    async with session_scope() as session:
        try:
            return await day_ops.get_drill_session(
                session, session_id, user_id=_user_id(settings)
            )
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/v1/drill/sessions",
    dependencies=[Depends(require_api_key)],
)
async def start_drill_session(
    body: DrillSessionStart,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    user_id = _user_id(settings)
    async with session_scope() as session:
        resume = await day_ops.get_resume(session, user_id=user_id)
        if resume is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="no resume imported yet; upload a resume first",
            )
        project: Project | None = None
        if body.project_id is not None:
            try:
                project = await day_ops.get_project(session, body.project_id, user_id=user_id)
            except KeyError as exc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
                ) from exc
        materials = await day_ops.list_drill_materials(session, user_id=user_id)
        ds = await day_ops.create_drill_session(
            session,
            resume_id=resume.id,
            round_=body.round,
            direction=body.direction,
            project_id=body.project_id,
            user_id=user_id,
        )

        verdict = await _run_sage(
            settings,
            session,
            user_id=user_id,
            resume=resume.document,
            materials=materials,
            project=project,
            round_=body.round,
            direction=body.direction,
            answer=None,
        )
        await day_ops.append_drill_message(
            session, ds.id, role="examiner", text=verdict.follow_up or "", user_id=user_id
        )
        if verdict.done:
            await day_ops.finish_drill_session(session, ds.id, user_id=user_id)
        return {"session": ds.model_dump(mode="json"), "verdict": verdict.model_dump(mode="json")}


@router.post(
    "/v1/drill/sessions/{session_id}",
    dependencies=[Depends(require_api_key)],
)
async def continue_drill_session(
    session_id: UUID,
    body: DrillSessionContinue,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    user_id = _user_id(settings)
    async with session_scope() as session:
        try:
            ds = await day_ops.get_drill_session(session, session_id, user_id=user_id)
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        if ds.status == "done":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="session already done"
            )
        resume = await day_ops.get_resume(session, user_id=user_id)
        if resume is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="no resume")
        project: Project | None = None
        if ds.project_id is not None:
            try:
                project = await day_ops.get_project(session, ds.project_id, user_id=user_id)
            except KeyError:
                project = None
        materials = await day_ops.list_drill_materials(session, user_id=user_id)

        await day_ops.append_drill_message(
            session, ds.id, role="user", text=body.answer, user_id=user_id
        )
        verdict = await _run_sage(
            settings,
            session,
            user_id=user_id,
            resume=resume.document,
            materials=materials,
            project=project,
            round_=ds.round,
            direction=ds.direction,
            answer=body.answer,
        )
        await day_ops.append_drill_message(
            session, ds.id, role="examiner", text=verdict.follow_up or "", user_id=user_id
        )
        if verdict.done:
            await day_ops.finish_drill_session(session, ds.id, user_id=user_id)
        return {"verdict": verdict.model_dump(mode="json")}


# --- helpers ---


def _resume_ext(content_type: str) -> str:
    return {
        "application/pdf": "pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "text/plain": "txt",
        "text/markdown": "md",
    }[content_type]


async def _active_prompt(settings: Settings, agent_name: str) -> str:
    async with session_scope() as session:
        prompt = await SessionPromptReader(session).get_active_prompt(agent_name)
        return prompt.system_prompt if prompt else ""


async def _run_sage(
    settings: Settings,
    session: AsyncSession,
    *,
    user_id: str,
    resume: ResumeDocument,
    materials: list[DrillMaterial],
    project: Project | None,
    round_: DrillRound,
    direction: str | None,
    answer: str | None,
) -> SageVerdict:
    if not settings.llm_api_key:
        return stub_sage(round_=round_, project=project, answer=answer)
    system_prompt = await SessionPromptReader(session).get_active_prompt("sage")
    system_prompt_text = system_prompt.system_prompt if system_prompt else ""
    reader = SessionMemoryReader(session, user_id=user_id)
    agent = build_sage_agent(get_model(), system_prompt=system_prompt_text)
    return await run_sage(
        agent,
        reader,
        resume=resume,
        materials=materials,
        project=project,
        round_=round_,
        direction=direction,
        answer=answer,
    )
