"""OpenClaw shell writeback + observation endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from gotit.api.auth import require_api_key
from gotit.api.deps import get_model
from gotit.api.routes._common import _user_id
from gotit.api.settings import Settings, get_settings
from gotit.core.cron_suggest import normalize_cron, suggest_cron_from_text
from gotit.core.models import (
    DigestCronSuggestRequest,
    DigestCronSuggestResult,
    DigestCronSyncResult,
    DigestPrefs,
    GraphView,
    InterestPromoteResult,
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
a.btn{display:inline-block;padding:.85rem 1.25rem;border-radius:980px;
background:#1d1d1f;color:#fff;text-decoration:none}
.hint{margin-top:1.25rem;font-size:.8rem;color:#86868b}
</style>
<script>
(function(){
var t=["mobilenotes://","notes://"],i=0;
function g(){if(i>=t.length)return;location.href=t[i++];setTimeout(g,400)}
g();
})();
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


class InterestPromoteRequest(BaseModel):
    """Optional rewrite texts after a vacuous reject (max 3)."""

    claim_texts: list[str] = Field(default_factory=list, max_length=3)


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


@router.post(
    "/v1/shell/interests/{interest_id}/promote",
    response_model=InterestPromoteResult,
    dependencies=[Depends(require_api_key)],
)
async def promote_interest(
    interest_id: UUID,
    settings: Annotated[Settings, Depends(get_settings)],
    body: InterestPromoteRequest | None = None,
) -> InterestPromoteResult:
    """Promote a marked-useful interest into 1–3 testable claims on today's plan."""
    from gotit.api.deps import SessionMemoryReader, SessionPromptReader
    from gotit.core.agents.compass import build_compass_agent, run_compass
    from gotit.core.models import Claim, MasteryStatus
    from gotit.db.models import MemoryEntryRow

    payload = body or InterestPromoteRequest()
    user_id = _user_id(settings)
    claim_texts = [t.strip() for t in payload.claim_texts if t.strip()][:3]
    claims: list[Claim] | None = None

    if not claim_texts and settings.llm_api_key:
        async with session_scope() as session:
            row = await session.get(MemoryEntryRow, interest_id)
            if row is None or row.user_id != user_id or row.kind != "interest":
                raise HTTPException(
                    status_code=404, detail=f"interest not found: {interest_id}"
                )
            material = day_ops.interest_material(dict(row.content or {}))
            if not material:
                raise HTTPException(status_code=400, detail="interest has no title")
            prompt = await SessionPromptReader(session).get_active_prompt("compass")
            system_prompt = prompt.system_prompt if prompt else ""
            reader = SessionMemoryReader(session, user_id=user_id)
            agent = build_compass_agent(get_model(), system_prompt=system_prompt)
            output = await run_compass(agent, reader, note_body=material)
        claims = [
            Claim(
                text=c.text,
                source_excerpt=(c.source_excerpt or material)[:200],
                status=MasteryStatus.NOT_YET,
                topic=c.topic,
                tags=list(c.tags) or ["digest", "interest"],
            )
            for c in output.claims[:3]
        ]
        if not claims:
            claims = None

    try:
        async with session_scope() as session:
            return await day_ops.promote_interest(
                session,
                interest_id,
                user_id=user_id,
                claims=claims,
                claim_texts=claim_texts or None,
            )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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
    "/v1/shell/digest-cron/suggest",
    response_model=DigestCronSuggestResult,
    dependencies=[Depends(require_api_key)],
)
async def suggest_digest_cron(
    body: DigestCronSuggestRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DigestCronSuggestResult:
    """Turn natural language into a 5-field cron (rule first, LLM fallback)."""
    text = body.text.strip()
    ruled = suggest_cron_from_text(text)
    if ruled:
        return DigestCronSuggestResult(
            cron=ruled,
            explanation=f"已根据「{text}」解析",
            source="rule",
        )

    if not settings.llm_api_key:
        raise HTTPException(
            status_code=400,
            detail=(
                "无法解析该时间描述。可试「每天早上9点」或「21:30」，"
                "或配置 LLM 后再用 AI 生成。"
            ),
        )

    from pydantic_ai import Agent

    agent: Agent[None, str] = Agent(
        get_model(),
        output_type=str,
        system_prompt=(
            "你把用户的中文或英文时间描述转成标准 5 段 cron（minute hour day month weekday）。"
            "只输出一行 cron，例如 `0 9 * * *`，不要解释、不要 markdown。"
            "默认每天重复（day/month/weekday 用 *）。无法确定时输出空字符串。"
        ),
        name="cron_suggest",
    )
    result = await agent.run(
        f"目标用途：{body.target}（morning=早推计划 / evening=晚推计划 / news=资讯）\n"
        f"用户说：{text}"
    )
    cron = normalize_cron(str(result.output or ""))
    if not cron:
        raise HTTPException(
            status_code=400,
            detail="AI 未能生成有效 cron，请改写为更明确的时间（如「每天晚上 9 点」）。",
        )
    return DigestCronSuggestResult(
        cron=cron,
        explanation=f"AI 根据「{text}」生成",
        source="llm",
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
