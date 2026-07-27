from __future__ import annotations

from datetime import date
from uuid import UUID

import anyio
from mcp.server.fastmcp import FastMCP

from gotit import __version__
from gotit.api.settings import get_settings
from gotit.core.models import CheckMode, PlanItemSource, PlanItemStatus
from gotit.db import ops as day_ops
from gotit.db import session_scope
from gotit.db.models import ClaimRow
from gotit.db.runtime import ensure_db

mcp = FastMCP("gotit")


def _user_id() -> str:
    return get_settings().gotit_user_id


@mcp.tool()
def gotit_health() -> dict[str, str]:
    """Return gotit-ai service health and version."""
    return {"status": "ok", "version": __version__}


@mcp.tool()
async def gotit_ingest(material: str) -> dict[str, object]:
    """Ingest study material and return stub claims (Librarian not wired yet)."""
    await ensure_db()
    claim = day_ops.stub_extract_claim(material)
    async with session_scope() as session:
        session.add(
            ClaimRow(
                id=claim.id,
                user_id=_user_id(),
                text=claim.text,
                source_excerpt=claim.source_excerpt,
                status=claim.status.value,
                source_note_id=None,
                next_review_at=None,
            )
        )
    return {
        "claims": [claim.model_dump(mode="json")],
        "state": "claim",
        "note": "stub: claim extraction not wired yet",
    }


@mcp.tool()
async def gotit_examine(
    claim_id: str,
    mode: str = CheckMode.PROBE.value,
    passed: bool | None = None,
) -> dict[str, object]:
    """Run an Examiner check for a claim (stub). Optional passed writeback."""
    await ensure_db()
    result: dict[str, object] = {
        "claim_id": claim_id,
        "mode": mode,
        "status": "stub",
        "message": "Examiner not wired yet",
    }
    if passed is not None:
        async with session_scope() as session:
            writeback = await day_ops.apply_examine_result(
                session,
                UUID(claim_id),
                passed=passed,
                user_id=_user_id(),
            )
        result["writeback"] = writeback
    return result


@mcp.tool()
async def gotit_today(day: str | None = None) -> dict[str, object]:
    """Aggregate today's plan, truncated notes, and due claims."""
    await ensure_db()
    target = date.fromisoformat(day) if day else None
    async with session_scope() as session:
        view = await day_ops.get_today(session, target, user_id=_user_id())
    return view.model_dump(mode="json")


@mcp.tool()
async def gotit_get_plan(day: str) -> dict[str, object]:
    """Get the learning plan for a YYYY-MM-DD day."""
    await ensure_db()
    async with session_scope() as session:
        view = await day_ops.get_plan(session, date.fromisoformat(day), user_id=_user_id())
    return view.model_dump(mode="json")


@mcp.tool()
async def gotit_upsert_plan_item(
    day: str,
    title: str,
    item_id: str | None = None,
    source: str = PlanItemSource.MANUAL.value,
    status: str = PlanItemStatus.PLANNED.value,
    claim_id: str | None = None,
    sort_order: int | None = None,
    due_at: str | None = None,
) -> dict[str, object]:
    """Create or update a plan item for a day."""
    await ensure_db()
    async with session_scope() as session:
        view = await day_ops.upsert_plan_item(
            session,
            date.fromisoformat(day),
            title=title,
            user_id=_user_id(),
            item_id=UUID(item_id) if item_id else None,
            source=PlanItemSource(source),
            status=PlanItemStatus(status),
            claim_id=UUID(claim_id) if claim_id else None,
            sort_order=sort_order,
            due_at=date.fromisoformat(due_at) if due_at else None,
        )
    return view.model_dump(mode="json")


@mcp.tool()
async def gotit_fill_today_from_queue(day: str | None = None) -> dict[str, object]:
    """Fill the day's plan from due / not-yet claims."""
    await ensure_db()
    target = date.fromisoformat(day) if day else date.today()
    async with session_scope() as session:
        view = await day_ops.fill_today_from_queue(session, target, user_id=_user_id())
    return view.model_dump(mode="json")


@mcp.tool()
async def gotit_update_plan_item(
    item_id: str,
    title: str | None = None,
    status: str | None = None,
    sort_order: int | None = None,
    due_at: str | None = None,
    defer_to: str | None = None,
) -> dict[str, object]:
    """Patch a plan item (status, defer, reorder)."""
    await ensure_db()
    async with session_scope() as session:
        view = await day_ops.update_plan_item(
            session,
            UUID(item_id),
            title=title,
            status=PlanItemStatus(status) if status else None,
            sort_order=sort_order,
            due_at=date.fromisoformat(due_at) if due_at else None,
            defer_to=date.fromisoformat(defer_to) if defer_to else None,
            user_id=_user_id(),
        )
    return view.model_dump(mode="json")


@mcp.tool()
async def gotit_list_notes(day: str) -> list[dict[str, object]]:
    """List notes for a day (bodies truncated to excerpts)."""
    await ensure_db()
    async with session_scope() as session:
        notes = await day_ops.list_notes(
            session,
            date.fromisoformat(day),
            user_id=_user_id(),
            full_body=False,
        )
    return [n.model_dump(mode="json") for n in notes]


@mcp.tool()
async def gotit_add_note(
    day: str,
    body: str,
    title: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, object]:
    """Add a study note for a day."""
    await ensure_db()
    async with session_scope() as session:
        note = await day_ops.add_note(
            session,
            date.fromisoformat(day),
            body,
            title=title,
            tags=tags,
            user_id=_user_id(),
        )
    return note.model_dump(mode="json")


@mcp.tool()
async def gotit_ingest_note(note_id: str, add_plan_item: bool = True) -> dict[str, object]:
    """Ingest a stored note into claims (stub extraction) and optionally a plan item."""
    await ensure_db()
    async with session_scope() as session:
        return await day_ops.ingest_note(
            session,
            UUID(note_id),
            user_id=_user_id(),
            add_plan_item=add_plan_item,
        )


def main() -> None:
    # stdio transport for local OpenClaw / MCP hosts
    anyio.run(mcp.run_stdio_async)


if __name__ == "__main__":
    main()
