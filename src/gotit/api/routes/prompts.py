"""Prompt observation + registration endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from gotit.api.auth import require_api_key
from gotit.api.settings import Settings, get_settings
from gotit.core.models import PromptVersion
from gotit.db import ops as day_ops
from gotit.db import session_scope
from gotit.prompts import load_prompt_dir

router = APIRouter()


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
