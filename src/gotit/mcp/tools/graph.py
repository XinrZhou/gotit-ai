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
async def gotit_add_depends_on(claim_id: str, prereq_claim_id: str) -> dict[str, object]:
    """Add directed depends_on: claim must wait on prereq (out-degree cap 3)."""

    await ensure_db()
    try:
        async with session_scope() as session:
            row = await day_ops.add_depends_on(
                session,
                user_id=_user_id(),
                claim_id=UUID(claim_id),
                prereq_claim_id=UUID(prereq_claim_id),
            )
    except KeyError as exc:
        return {"ok": False, "error": str(exc)}
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    return {
        "ok": True,
        "claim_id": str(row.source_claim_id),
        "prereq_claim_id": str(row.target_claim_id),
        "rel": "depends_on",
    }

@mcp.tool()
async def gotit_remove_depends_on(
    claim_id: str, prereq_claim_id: str
) -> dict[str, object]:
    """Remove a depends_on edge."""

    await ensure_db()
    async with session_scope() as session:
        removed = await day_ops.remove_depends_on(
            session,
            user_id=_user_id(),
            claim_id=UUID(claim_id),
            prereq_claim_id=UUID(prereq_claim_id),
        )
    return {"ok": removed, "removed": removed}

@mcp.tool()
async def gotit_list_depends_on(claim_id: str | None = None) -> list[dict[str, object]]:
    """List depends_on edges (optionally for one dependent claim)."""

    await ensure_db()
    cid = UUID(claim_id) if claim_id else None
    async with session_scope() as session:
        rows = await day_ops.list_depends_edges(
            session, user_id=_user_id(), claim_id=cid
        )
    return [
        {
            "claim_id": str(r.source_claim_id),
            "prereq_claim_id": str(r.target_claim_id),
            "rel": "depends_on",
        }
        for r in rows
    ]

