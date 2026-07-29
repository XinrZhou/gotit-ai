"""Skills settings API — catalog, install, enable, delete."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from gotit.api.auth import require_api_key
from gotit.api.routes._common import _user_id
from gotit.api.settings import Settings, get_settings
from gotit.core.models import SkillInfo
from gotit.db import ops as day_ops
from gotit.db import session_scope

router = APIRouter()


class SkillInstallBody(BaseModel):
    markdown: str = Field(min_length=1, description="SKILL.md / skill markdown content")
    name: str | None = Field(
        default=None,
        description="Fallback name when frontmatter omits skill/name",
    )


class SkillPatchBody(BaseModel):
    enabled: bool


@router.get(
    "/v1/skills",
    response_model=list[SkillInfo],
    dependencies=[Depends(require_api_key)],
)
async def list_skills(
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[SkillInfo]:
    async with session_scope() as session:
        return await day_ops.list_skill_catalog(session, user_id=_user_id(settings))


@router.post(
    "/v1/skills",
    response_model=SkillInfo,
    dependencies=[Depends(require_api_key)],
)
async def install_skill(
    body: SkillInstallBody,
    settings: Annotated[Settings, Depends(get_settings)],
) -> SkillInfo:
    try:
        async with session_scope() as session:
            return await day_ops.install_skill(
                session,
                user_id=_user_id(settings),
                raw_markdown=body.markdown,
                fallback_name=body.name,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch(
    "/v1/skills/{name}",
    response_model=SkillInfo,
    dependencies=[Depends(require_api_key)],
)
async def patch_skill(
    name: str,
    body: SkillPatchBody,
    settings: Annotated[Settings, Depends(get_settings)],
) -> SkillInfo:
    try:
        async with session_scope() as session:
            return await day_ops.set_skill_enabled(
                session,
                user_id=_user_id(settings),
                name=name,
                enabled=body.enabled,
            )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete(
    "/v1/skills/{name}",
    status_code=204,
    dependencies=[Depends(require_api_key)],
)
async def delete_skill(
    name: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    try:
        async with session_scope() as session:
            await day_ops.delete_user_skill(
                session,
                user_id=_user_id(settings),
                name=name,
            )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
