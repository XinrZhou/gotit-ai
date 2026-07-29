"""OpenClaw shell writeback + observation endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from gotit.api.auth import require_api_key
from gotit.api.routes._common import _user_id
from gotit.api.settings import Settings, get_settings
from gotit.core.models import (
    DigestCronSyncResult,
    DigestPrefs,
    GraphView,
    MemoryEntry,
    ProfileView,
)
from gotit.db import ops as day_ops
from gotit.db import session_scope

router = APIRouter()

_OPEN_NOTES_HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>打开备忘录</title>
<meta http-equiv="refresh" content="0;url=mobilenotes://"/>
<style>
body{margin:0;min-height:100vh;display:grid;place-items:center;padding:24px;
font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#f5f5f7;color:#1d1d1f}
main{max-width:22rem;text-align:center}
a.btn{display:inline-block;padding:.85rem 1.25rem;border-radius:980px;background:#1d1d1f;color:#fff;text-decoration:none}
.hint{margin-top:1.25rem;font-size:.8rem;color:#86868b}
</style>
<script>
(function(){var t=["mobilenotes://","notes://"],i=0;function g(){if(i>=t.length)return;location.href=t[i++];setTimeout(g,400)}g();})();
</script>
</head><body><main>
<h1>打开备忘录</h1>
<p>若未自动跳转请点按钮。微信内无效时：右上角···→在 Safari 中打开。</p>
<p><a class="btn" href="mobilenotes://">打开备忘录 App</a></p>
<p class="hint">写完回微信回复「导入计划」。</p>
</main></body></html>
"""


def _notes_bridge_file() -> Path | None:
    here = Path(__file__).resolve()
    for root in (here.parents[4], Path.cwd()):
        candidate = root / "skills" / "digest" / "open-notes.html"
        if candidate.is_file():
            return candidate
    return None


@router.get("/open/notes", response_model=None, include_in_schema=True)
async def open_notes_app_bridge() -> FileResponse | HTMLResponse:
    """Public https bridge → mobilenotes:// (WeChat needs https to show a tappable link)."""
    path = _notes_bridge_file()
    if path is not None:
        return FileResponse(path, media_type="text/html; charset=utf-8")
    return HTMLResponse(_OPEN_NOTES_HTML)


class ShellEventCreate(BaseModel):
    job: str = Field(min_length=1, max_length=64)
    items: list[dict[str, Any]] = Field(default_factory=list)
    due_summary: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    delivery_ok: bool | None = None
    channel: str = "openclaw-weixin"
    skill: str = "digest"
    run_id: str | None = None
    subject: str | None = Field(default=None, max_length=500)
    day: str | None = Field(default=None, max_length=32)


class InterestCreate(BaseModel):
    event_id: UUID
    item_index: int = Field(ge=1, le=50)
    title: str = Field(min_length=1, max_length=500)
    link: str | None = None
    feed_id: str | None = None
    topic: str | None = None
    channel: str = "openclaw-weixin"
    skill: str = "digest"


@router.post(
    "/v1/shell/events",
    response_model=MemoryEntry,
    dependencies=[Depends(require_api_key)],
)
async def create_shell_event(
    body: ShellEventCreate,
    settings: Annotated[Settings, Depends(get_settings)],
) -> MemoryEntry:
    async with session_scope() as session:
        return await day_ops.record_shell_event(
            session,
            user_id=_user_id(settings),
            job=body.job,
            items=body.items,
            due_summary=body.due_summary,
            errors=body.errors,
            delivery_ok=body.delivery_ok,
            channel=body.channel,
            skill=body.skill,
            run_id=body.run_id,
            subject=body.subject,
            day=body.day,
        )


@router.post(
    "/v1/shell/interest",
    response_model=MemoryEntry,
    dependencies=[Depends(require_api_key)],
)
async def create_interest(
    body: InterestCreate,
    settings: Annotated[Settings, Depends(get_settings)],
) -> MemoryEntry:
    async with session_scope() as session:
        return await day_ops.record_interest(
            session,
            user_id=_user_id(settings),
            event_id=body.event_id,
            item_index=body.item_index,
            title=body.title,
            link=body.link,
            feed_id=body.feed_id,
            topic=body.topic,
            channel=body.channel,
            skill=body.skill,
        )


@router.get(
    "/v1/shell/activity",
    response_model=list[MemoryEntry],
    dependencies=[Depends(require_api_key)],
)
async def shell_activity(
    settings: Annotated[Settings, Depends(get_settings)],
    kinds: Annotated[str | None, Query(description="Comma: shell_event,interest")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[MemoryEntry]:
    kind_list = [k.strip() for k in kinds.split(",")] if kinds else None
    if kind_list is not None:
        kind_list = [k for k in kind_list if k]
        if not kind_list:
            raise HTTPException(status_code=400, detail="kinds empty")
    async with session_scope() as session:
        return await day_ops.list_shell_activity(
            session,
            user_id=_user_id(settings),
            kinds=kind_list,
            limit=limit,
        )


@router.get(
    "/v1/shell/digest-prefs",
    response_model=DigestPrefs,
    dependencies=[Depends(require_api_key)],
)
async def get_digest_prefs(
    settings: Annotated[Settings, Depends(get_settings)],
) -> DigestPrefs:
    async with session_scope() as session:
        return await day_ops.get_digest_prefs(session, user_id=_user_id(settings))


@router.put(
    "/v1/shell/digest-prefs",
    response_model=DigestPrefs,
    dependencies=[Depends(require_api_key)],
)
async def put_digest_prefs(
    body: DigestPrefs,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DigestPrefs:
    async with session_scope() as session:
        return await day_ops.put_digest_prefs(
            session, body, user_id=_user_id(settings)
        )


@router.post(
    "/v1/shell/digest-cron/sync",
    response_model=DigestCronSyncResult,
    dependencies=[Depends(require_api_key)],
)
async def sync_digest_cron() -> DigestCronSyncResult:
    """Re-register OpenClaw cron from current digest_prefs (runs install-cron.sh)."""
    return day_ops.sync_digest_openclaw_cron()


@router.get(
    "/v1/obs/profile",
    response_model=ProfileView,
    dependencies=[Depends(require_api_key)],
)
async def obs_profile(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ProfileView:
    async with session_scope() as session:
        return await day_ops.build_profile_v0(session, user_id=_user_id(settings))


@router.get(
    "/v1/obs/graph",
    response_model=GraphView,
    dependencies=[Depends(require_api_key)],
)
async def obs_graph(
    settings: Annotated[Settings, Depends(get_settings)],
) -> GraphView:
    async with session_scope() as session:
        return await day_ops.build_graph_v0(session, user_id=_user_id(settings))
