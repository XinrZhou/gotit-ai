from __future__ import annotations

from datetime import date
from uuid import UUID

from gotit.core.models import (
    PlanItemSource,
    PlanItemStatus,
)
from gotit.db import ops as day_ops
from gotit.db import session_scope
from gotit.db.runtime import ensure_db
from gotit.mcp.app import mcp
from gotit.mcp.common import (
    _user_id,
)


@mcp.tool()
async def gotit_today(day: str | None = None) -> dict[str, object]:
    """Aggregate today's plan, truncated notes, due claims, and day-close state."""
    await ensure_db()
    target = date.fromisoformat(day) if day else None
    async with session_scope() as session:
        view = await day_ops.get_today(session, target, user_id=_user_id())
    return view.model_dump(mode="json")

@mcp.tool()
async def gotit_close_day(
    day: str | None = None,
    note: str | None = None,
) -> dict[str, object]:
    """Close the learning day (idempotent). Returns wrap counts for evening digest."""
    await ensure_db()
    target = date.fromisoformat(day) if day else None
    async with session_scope() as session:
        summary = await day_ops.close_today(
            session, target, user_id=_user_id(), note=note
        )
    return summary.model_dump(mode="json")

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
    due_time: str | None = None,
) -> dict[str, object]:
    """Create or update a plan item. Pass due_time=HH:MM when known (Reminders).

    Best-effort syncs to Apple Reminders after write (same Mac as OpenClaw).
    """
    await ensure_db()
    day_d = date.fromisoformat(day)
    async with session_scope() as session:
        view = await day_ops.upsert_plan_item(
            session,
            day_d,
            title=title,
            user_id=_user_id(),
            item_id=UUID(item_id) if item_id else None,
            source=PlanItemSource(source),
            status=PlanItemStatus(status),
            claim_id=UUID(claim_id) if claim_id else None,
            sort_order=sort_order,
            due_at=date.fromisoformat(due_at) if due_at else None,
            due_time=due_time,
        )
    from gotit.bridge.reminders import push_day

    apple_err = push_day(day_d, title=view.title, time=view.due_time)
    out = view.model_dump(mode="json")
    if apple_err:
        out["apple_sync_error"] = apple_err
    else:
        out["apple_synced"] = True
    return out

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
    due_time: str | None = None,
    defer_to: str | None = None,
) -> dict[str, object]:
    """Patch a plan item (status, defer, reorder, due_time). Syncs Reminders for the day."""
    await ensure_db()
    plan_day: date | None = None
    async with session_scope() as session:
        view = await day_ops.update_plan_item(
            session,
            UUID(item_id),
            title=title,
            status=PlanItemStatus(status) if status else None,
            sort_order=sort_order,
            due_at=date.fromisoformat(due_at) if due_at else None,
            due_time=due_time,
            defer_to=date.fromisoformat(defer_to) if defer_to else None,
            user_id=_user_id(),
        )
        from gotit.db.models import LearningDayRow, PlanItemRow

        row = await session.get(PlanItemRow, UUID(item_id))
        if row is not None:
            day_row = await session.get(LearningDayRow, row.day_id)
            if day_row is not None:
                plan_day = day_row.day
    out = view.model_dump(mode="json")
    if plan_day is not None:
        from gotit.bridge.reminders import push_day

        apple_err = push_day(plan_day, reconcile=True)
        if apple_err:
            out["apple_sync_error"] = apple_err
        else:
            out["apple_synced"] = True
    return out

@mcp.tool()
async def gotit_delete_plan_item(
    item_id: str | None = None,
    day: str | None = None,
    title: str | None = None,
) -> dict[str, object]:
    """Delete a plan item by id, or by day + title (casefold exact match).

    Also removes the matching incomplete Reminder (best-effort).
    """
    await ensure_db()
    uid = _user_id()
    async with session_scope() as session:
        matched_title = (title or "").strip() or None
        matched_day = day
        if item_id:
            target_id = UUID(item_id)
            from gotit.db.models import LearningDayRow, PlanItemRow

            row = await session.get(PlanItemRow, target_id)
            if row is not None:
                matched_title = row.title
                day_row = await session.get(LearningDayRow, row.day_id)
                if day_row is not None:
                    matched_day = day_row.day.isoformat()
        else:
            if not day or not matched_title:
                raise ValueError("provide item_id, or both day and title")
            plan = await day_ops.get_plan(
                session, date.fromisoformat(day), user_id=uid
            )
            needle = matched_title.casefold()
            hits = [
                i for i in plan.items if (i.title or "").strip().casefold() == needle
            ]
            if not hits:
                raise KeyError(f"plan item not found: day={day} title={title!r}")
            if len(hits) > 1:
                ids = ", ".join(str(h.id) for h in hits)
                raise ValueError(
                    f"multiple plan items match title={title!r} on {day}; "
                    f"pass item_id explicitly ({ids})"
                )
            target_id = hits[0].id
            matched_title = hits[0].title
        await day_ops.delete_plan_item(session, target_id, user_id=uid)
    out: dict[str, object] = {
        "ok": True,
        "deleted_id": str(target_id),
        "day": matched_day,
        "title": matched_title,
    }
    if matched_title and matched_day:
        from gotit.bridge.reminders import rm_item

        apple_err = rm_item(date.fromisoformat(matched_day), matched_title)
        if apple_err:
            out["apple_sync_error"] = apple_err
        else:
            out["apple_synced"] = True
    return out

