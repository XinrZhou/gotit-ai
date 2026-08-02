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
async def gotit_list_memory(
    layer: str | None = None,
    kind: str | None = None,
    topic: str | None = None,
    limit: int = 50,
) -> list[dict[str, object]]:
    """List memory entries (filtered by layer/kind/topic)."""
    await ensure_db()
    async with session_scope() as session:
        entries = await day_ops.list_memory(
            session,
            user_id=_user_id(),
            layer=layer,
            kind=kind,
            topic=topic,
            limit=limit,
        )
    return [e.model_dump(mode="json") for e in entries]

@mcp.tool()
async def gotit_add_memory(
    layer: str,
    kind: str,
    content: dict[str, object] | None = None,
    topic: str | None = None,
    source: dict[str, object] | None = None,
) -> dict[str, object]:
    """Add a memory entry (long/working/session)."""
    await ensure_db()
    async with session_scope() as session:
        entry = await day_ops.add_memory(
            session,
            user_id=_user_id(),
            layer=layer,
            kind=kind,
            content=content or {},
            topic=topic,
            source=source,
        )
    return entry.model_dump(mode="json")

@mcp.tool()
async def gotit_list_pending_failure_digests(limit: int = 20) -> list[dict[str, object]]:
    """Pending examine failure digests (almost|owe_next) not yet sent to WeChat."""
    await ensure_db()
    async with session_scope() as session:
        entries = await day_ops.list_pending_failure_digests(
            session, user_id=_user_id(), limit=limit
        )
    return [e.model_dump(mode="json") for e in entries]

@mcp.tool()
async def gotit_mark_failure_digest_notified(memory_id: str) -> dict[str, object]:
    """Mark a failure_digest memory as delivered (WeChat)."""
    await ensure_db()
    async with session_scope() as session:
        entry = await day_ops.mark_failure_digest_notified(
            session, UUID(memory_id), user_id=_user_id()
        )
    return entry.model_dump(mode="json")

