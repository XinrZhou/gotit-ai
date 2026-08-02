from __future__ import annotations

from uuid import UUID

from gotit.db import ops as day_ops
from gotit.db import session_scope
from gotit.db.runtime import ensure_db
from gotit.mcp.app import mcp
from gotit.mcp.common import (
    _user_id,
)


@mcp.tool()
async def gotit_record_shell_event(
    job: str,
    items: list[dict[str, object]] | None = None,
    due_summary: list[str] | None = None,
    errors: list[str] | None = None,
    delivery_ok: bool | None = None,
    channel: str = "openclaw-weixin",
    skill: str = "digest",
    run_id: str | None = None,
    subject: str | None = None,
    day: str | None = None,
) -> dict[str, object]:
    """Record an OpenClaw plan/news push as kind=shell_event (obs truth)."""
    await ensure_db()
    async with session_scope() as session:
        entry = await day_ops.record_shell_event(
            session,
            user_id=_user_id(),
            job=job,
            items=items,
            due_summary=due_summary,
            errors=errors,
            delivery_ok=delivery_ok,
            channel=channel,
            skill=skill,
            run_id=run_id,
            subject=subject,
            day=day,
        )
    return entry.model_dump(mode="json")

@mcp.tool()
async def gotit_record_interest(
    event_id: str,
    item_index: int,
    title: str,
    link: str | None = None,
    feed_id: str | None = None,
    topic: str | None = None,
    channel: str = "openclaw-weixin",
    skill: str = "digest",
) -> dict[str, object]:
    """Record 「这篇有用」 as kind=interest (no ingest)."""
    await ensure_db()
    async with session_scope() as session:
        entry = await day_ops.record_interest(
            session,
            user_id=_user_id(),
            event_id=event_id,
            item_index=item_index,
            title=title,
            link=link,
            feed_id=feed_id,
            topic=topic,
            channel=channel,
            skill=skill,
        )
    return entry.model_dump(mode="json")

@mcp.tool()
async def gotit_promote_interest(
    interest_id: str,
    claim_texts: list[str] | None = None,
) -> dict[str, object]:
    """Promote a marked-useful interest into 1–3 claims on today's plan."""
    await ensure_db()
    texts = [t.strip() for t in (claim_texts or []) if str(t).strip()][:3]
    async with session_scope() as session:
        result = await day_ops.promote_interest(
            session,
            UUID(interest_id),
            user_id=_user_id(),
            claim_texts=texts or None,
        )
    return result.model_dump(mode="json")

@mcp.tool()
async def gotit_list_shell_activity(
    kinds: str | None = None,
    limit: int = 50,
) -> list[dict[str, object]]:
    """List shell_event / interest activity (comma kinds, newest first)."""
    await ensure_db()
    kind_list = [k.strip() for k in kinds.split(",")] if kinds else None
    async with session_scope() as session:
        entries = await day_ops.list_shell_activity(
            session,
            user_id=_user_id(),
            kinds=kind_list,
            limit=limit,
        )
    return [e.model_dump(mode="json") for e in entries]

@mcp.tool()
async def gotit_get_digest_prefs() -> dict[str, object]:
    """Get OpenClaw digest prefs (plan cron + optional AI/YouTube feeds)."""
    await ensure_db()
    async with session_scope() as session:
        prefs = await day_ops.get_digest_prefs(session, user_id=_user_id())
    return prefs.model_dump(mode="json")

@mcp.tool()
async def gotit_put_digest_prefs(prefs: dict[str, object]) -> dict[str, object]:
    """Replace digest prefs (feeds, cron strings, news switch, keywords)."""
    from gotit.core.models import DigestPrefs

    await ensure_db()
    body = DigestPrefs.model_validate(prefs)
    async with session_scope() as session:
        saved = await day_ops.put_digest_prefs(session, body, user_id=_user_id())
    return saved.model_dump(mode="json")

@mcp.tool()
async def gotit_sync_digest_cron() -> dict[str, object]:
    """Re-register OpenClaw plan/news cron from current digest_prefs (install-cron.sh)."""
    result = day_ops.sync_digest_openclaw_cron()
    return result.model_dump(mode="json")

@mcp.tool()
async def gotit_obs_profile() -> dict[str, object]:
    """Profile v0: trajectory + interest aggregates by topic."""
    await ensure_db()
    async with session_scope() as session:
        view = await day_ops.build_profile_v0(session, user_id=_user_id())
    return view.model_dump(mode="json")

@mcp.tool()
async def gotit_obs_graph() -> dict[str, object]:
    """Graph v0: claim–topic–project edges; confuse + depends; interest→topic."""
    await ensure_db()
    async with session_scope() as session:
        view = await day_ops.build_graph_v0(session, user_id=_user_id())
    return view.model_dump(mode="json")

