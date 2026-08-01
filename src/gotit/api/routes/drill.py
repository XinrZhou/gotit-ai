"""Drill materials, material file import, and resume-driven mock-interview sessions."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from gotit.api.auth import require_api_key
from gotit.api.routes._common import (
    ALLOWED_RESUME_TYPES,
    MAX_RESUME_BYTES,
    _run_sage,
    _user_id,
)
from gotit.api.settings import Settings, get_settings
from gotit.api.workflow_persist import drill_agent_text
from gotit.core.models import DrillMaterial, DrillRound, DrillSession, Project
from gotit.core.resume.extract import ResumeExtractError, extract_text
from gotit.db import ops as day_ops
from gotit.db import session_scope

router = APIRouter()


class DrillMaterialIn(BaseModel):
    id: UUID | None = None
    title: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1)


class DrillSessionStart(BaseModel):
    round: DrillRound
    direction: str | None = None
    project_id: UUID | None = None
    thread_id: UUID | None = Field(
        default=None,
        description="When set, append drill turns into the companion thread stream.",
    )


class DrillSessionContinue(BaseModel):
    answer: str = Field(min_length=1)
    thread_id: UUID | None = Field(
        default=None,
        description="When set, append this turn into the companion thread stream.",
    )


async def _persist_drill(
    session: Any,
    *,
    thread_id: UUID | None,
    user_id: str,
    session_id: UUID,
    answer: str | None,
    agent_text: str,
    session_done: bool,
    title_seed: str | None = None,
) -> None:
    if thread_id is None:
        return
    try:
        await day_ops.append_workflow_exchange(
            session,
            thread_id=thread_id,
            user_id=user_id,
            workflow="drill",
            agent_name="sage",
            agent_text=agent_text,
            user_text=answer,
            extra_metadata={
                "drill_session_id": str(session_id),
                "session_done": session_done,
            },
            title_seed=title_seed,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


# --- Drill materials ---


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
        drill_title = (
            (project.name if project is not None else None)
            or (body.direction or "").strip()
            or "项目深挖"
        )
        await _persist_drill(
            session,
            thread_id=body.thread_id,
            user_id=user_id,
            session_id=ds.id,
            answer=None,
            agent_text=drill_agent_text(
                done=verdict.done,
                depth_reached=verdict.depth_reached,
                gaps=list(verdict.gaps),
                follow_up=verdict.follow_up,
            ),
            session_done=verdict.done,
            title_seed=drill_title,
        )
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
        cont_title = (
            (project.name if project is not None else None)
            or (ds.direction or "").strip()
            or "项目深挖"
        )
        await _persist_drill(
            session,
            thread_id=body.thread_id,
            user_id=user_id,
            session_id=ds.id,
            answer=body.answer,
            agent_text=drill_agent_text(
                done=verdict.done,
                depth_reached=verdict.depth_reached,
                gaps=list(verdict.gaps),
                follow_up=verdict.follow_up,
            ),
            session_done=verdict.done,
            title_seed=cont_title,
        )
        return {"verdict": verdict.model_dump(mode="json")}
