"""First-pass bootcamp — skip / start / complete."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from gotit.api.auth import require_api_key
from gotit.api.routes._common import _user_id
from gotit.api.settings import Settings, get_settings
from gotit.core.models import BootcampView
from gotit.db import ops as day_ops
from gotit.db import session_scope

router = APIRouter()


class BootcampStatusBody(BaseModel):
    status: Literal["in_progress", "done", "skipped"] = Field(
        description="in_progress | done | skipped"
    )


@router.get(
    "/v1/bootcamp",
    response_model=BootcampView,
    dependencies=[Depends(require_api_key)],
)
async def get_bootcamp(
    settings: Annotated[Settings, Depends(get_settings)],
) -> BootcampView:
    async with session_scope() as session:
        return await day_ops.resolve_bootcamp(
            session, user_id=_user_id(settings)
        )


@router.put(
    "/v1/bootcamp",
    response_model=BootcampView,
    dependencies=[Depends(require_api_key)],
)
async def put_bootcamp(
    body: BootcampStatusBody,
    settings: Annotated[Settings, Depends(get_settings)],
) -> BootcampView:
    async with session_scope() as session:
        await day_ops.put_bootcamp_status(
            session, body.status, user_id=_user_id(settings)
        )
        return await day_ops.resolve_bootcamp(
            session, user_id=_user_id(settings)
        )
