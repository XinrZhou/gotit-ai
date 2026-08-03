from __future__ import annotations

from uuid import UUID

from gotit.core.models import (
    InterviewStatus,
)
from gotit.db import ops as day_ops
from gotit.db import session_scope
from gotit.db.runtime import ensure_db
from gotit.mcp.app import mcp
from gotit.mcp.common import (
    _user_id,
)


@mcp.tool()
async def gotit_list_interviews(include_done: bool = False) -> list[dict[str, object]]:
    """List scheduled real-world interviews (newest scheduled first)."""
    await ensure_db()
    async with session_scope() as session:
        rows = await day_ops.list_interviews(
            session, user_id=_user_id(), include_done=include_done
        )
    return [r.model_dump(mode="json") for r in rows]

@mcp.tool()
async def gotit_upsert_interview(
    company: str,
    role_title: str,
    scheduled_at: str,
    interview_id: str | None = None,
    round: str | None = None,
    status: str = "scheduled",
    notes: str | None = None,
    remind_offsets_hours: list[int] | None = None,
) -> dict[str, object]:
    """Create or update a real-world interview. `scheduled_at` is ISO-8601 tz-aware."""
    await ensure_db()
    from datetime import datetime

    async with session_scope() as session:
        row = await day_ops.upsert_interview(
            session,
            interview_id=UUID(interview_id) if interview_id else None,
            company=company,
            role_title=role_title,
            scheduled_at=datetime.fromisoformat(scheduled_at.replace("Z", "+00:00")),
            round=round,
            status=InterviewStatus(status),
            notes=notes,
            remind_offsets_hours=remind_offsets_hours,
            user_id=_user_id(),
        )
    from gotit.bridge.calendar import sync_interview_to_calendar

    out = row.model_dump(mode="json")
    apple_err = sync_interview_to_calendar(row)
    if apple_err:
        out["apple_sync_error"] = apple_err
    else:
        out["apple_synced"] = True
    return out

@mcp.tool()
async def gotit_update_interview_status(
    interview_id: str,
    status: str,
) -> dict[str, object]:
    """Update interview status: scheduled | done | cancelled."""
    await ensure_db()
    async with session_scope() as session:
        row = await day_ops.update_interview_status(
            session,
            UUID(interview_id),
            InterviewStatus(status),
            user_id=_user_id(),
        )
    from gotit.bridge.calendar import sync_interview_to_calendar

    out = row.model_dump(mode="json")
    apple_err = sync_interview_to_calendar(row)
    if apple_err:
        out["apple_sync_error"] = apple_err
    else:
        out["apple_synced"] = True
    return out

@mcp.tool()
async def gotit_list_due_interview_reminders(
    now: str | None = None,
) -> list[dict[str, object]]:
    """Return due interview reminders for OpenClaw cron (offset + fire_at)."""
    await ensure_db()
    from datetime import UTC, datetime

    at = (
        datetime.fromisoformat(now.replace("Z", "+00:00"))
        if now
        else datetime.now(UTC)
    )
    async with session_scope() as session:
        due = await day_ops.list_due_interview_reminders(session, at, user_id=_user_id())
    return [d.model_dump(mode="json") for d in due]

@mcp.tool()
async def gotit_mark_interview_reminded(
    interview_id: str,
    at: str | None = None,
) -> dict[str, object]:
    """Mark an interview reminder as sent (updates last_reminded_at)."""
    await ensure_db()
    from datetime import datetime

    reminded_at = (
        datetime.fromisoformat(at.replace("Z", "+00:00")) if at else None
    )
    async with session_scope() as session:
        row = await day_ops.mark_interview_reminded(
            session,
            UUID(interview_id),
            at=reminded_at,
            user_id=_user_id(),
        )
    return row.model_dump(mode="json")

@mcp.tool()
async def gotit_list_upcoming_interviews(
    now: str | None = None,
) -> list[dict[str, object]]:
    """Upcoming interviews (7d) with deterministic ramp_tier + suggest_action."""
    await ensure_db()
    from datetime import UTC, datetime

    at = (
        datetime.fromisoformat(now.replace("Z", "+00:00"))
        if now
        else datetime.now(UTC)
    )
    async with session_scope() as session:
        rows = await day_ops.list_upcoming_interviews(
            session, at, user_id=_user_id()
        )
    return [r.model_dump(mode="json") for r in rows]

@mcp.tool()
async def gotit_list_interview_ramp_nudges(
    now: str | None = None,
) -> list[dict[str, object]]:
    """Due countdown-ramp nudges (light/warm; prefs + cooldown). ≤1 item."""
    await ensure_db()
    from datetime import UTC, datetime

    at = (
        datetime.fromisoformat(now.replace("Z", "+00:00"))
        if now
        else datetime.now(UTC)
    )
    async with session_scope() as session:
        rows = await day_ops.list_interview_ramp_nudges(
            session, at, user_id=_user_id()
        )
    return [r.model_dump(mode="json") for r in rows]

@mcp.tool()
async def gotit_mark_interview_ramp_nudged(
    interview_id: str,
    at: str | None = None,
) -> dict[str, object]:
    """Mark a ramp nudge as delivered (updates last_ramp_nudge_at)."""
    await ensure_db()
    from datetime import datetime

    nudged_at = (
        datetime.fromisoformat(at.replace("Z", "+00:00")) if at else None
    )
    async with session_scope() as session:
        row = await day_ops.mark_interview_ramp_nudged(
            session,
            UUID(interview_id),
            at=nudged_at,
            user_id=_user_id(),
        )
    return row.model_dump(mode="json")

@mcp.tool()
async def gotit_get_interview_ramp_prefs() -> dict[str, object]:
    """Read interview countdown-ramp prefs (enabled / weekly cap)."""
    await ensure_db()
    async with session_scope() as session:
        prefs = await day_ops.get_interview_ramp_prefs(session, user_id=_user_id())
    return prefs.model_dump(mode="json")

@mcp.tool()
async def gotit_put_interview_ramp_prefs(prefs: dict[str, object]) -> dict[str, object]:
    """Update interview countdown-ramp prefs."""
    await ensure_db()
    from gotit.core.models import InterviewRampPrefs

    body = InterviewRampPrefs.model_validate(prefs)
    async with session_scope() as session:
        saved = await day_ops.put_interview_ramp_prefs(
            session, body, user_id=_user_id()
        )
    return saved.model_dump(mode="json")

