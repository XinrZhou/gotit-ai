"""Project library endpoints (projects come from resume parse; no manual create)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from gotit.api.auth import require_api_key
from gotit.api.routes._common import _user_id
from gotit.api.settings import Settings, get_settings
from gotit.core.models import Project, ProjectProgress, ProjectStatus
from gotit.db import ops as day_ops
from gotit.db import session_scope

router = APIRouter()


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


@router.delete(
    "/v1/projects/{project_id}",
    response_model=Project,
    dependencies=[Depends(require_api_key)],
)
async def delete_project(
    project_id: UUID,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Project:
    """Archive (soft-delete) so the project leaves the default library list."""
    async with session_scope() as session:
        try:
            return await day_ops.archive_project(
                session, project_id, user_id=_user_id(settings)
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
