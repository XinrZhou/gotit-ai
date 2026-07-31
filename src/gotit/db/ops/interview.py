"""Scheduled real-world interview events (companion-os P3d + P4 ramp)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gotit.core.interview_ramp import (
    DELIVERABLE_TIERS,
    LIGHT_HOURS,
    RAMP_NUDGE_COOLDOWN_HOURS,
    ramp_tier,
    suggest_action,
    tier_hint_zh,
)
from gotit.core.models import (
    DEFAULT_REMIND_OFFSETS_HOURS,
    DueInterviewReminder,
    InterviewEventView,
    InterviewRampNudge,
    InterviewRampPrefs,
    InterviewStatus,
    InterviewUpcoming,
)
from gotit.db.models import InterviewEventRow, MemoryEntryRow
from gotit.db.ops._common import DEFAULT_USER_ID

STALE_REMINDER_HOURS = 6
KIND_INTERVIEW_RAMP_PREFS = "interview_ramp_prefs"
UPCOMING_WITHIN_HOURS = LIGHT_HOURS  # 7d window for companion / Settings


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _interview_view(row: InterviewEventRow) -> InterviewEventView:
    offsets = row.remind_offsets_hours
    if not isinstance(offsets, list) or not offsets:
        offsets = list(DEFAULT_REMIND_OFFSETS_HOURS)
    return InterviewEventView(
        id=row.id,
        user_id=row.user_id,
        company=row.company,
        role_title=row.role_title,
        scheduled_at=row.scheduled_at,
        round=row.round,
        status=InterviewStatus(row.status),
        notes=row.notes,
        remind_offsets_hours=[int(x) for x in offsets],
        last_reminded_at=row.last_reminded_at,
        last_ramp_nudge_at=row.last_ramp_nudge_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def default_interview_ramp_prefs() -> InterviewRampPrefs:
    return InterviewRampPrefs()


def _ramp_prefs_from_content(content: dict[str, Any]) -> InterviewRampPrefs:
    base = default_interview_ramp_prefs().model_dump(mode="json")
    base.update(content or {})
    return InterviewRampPrefs.model_validate(base)


async def list_interviews(
    session: AsyncSession,
    *,
    user_id: str = DEFAULT_USER_ID,
    include_done: bool = False,
) -> list[InterviewEventView]:
    stmt = select(InterviewEventRow).where(InterviewEventRow.user_id == user_id)
    if not include_done:
        stmt = stmt.where(InterviewEventRow.status != InterviewStatus.DONE.value)
    stmt = stmt.order_by(InterviewEventRow.scheduled_at.asc())
    rows = list((await session.execute(stmt)).scalars().all())
    return [_interview_view(r) for r in rows]


async def upsert_interview(
    session: AsyncSession,
    *,
    interview_id: UUID | None = None,
    company: str,
    role_title: str,
    scheduled_at: datetime,
    round: str | None = None,
    status: InterviewStatus = InterviewStatus.SCHEDULED,
    notes: str | None = None,
    remind_offsets_hours: list[int] | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> InterviewEventView:
    now = datetime.now(UTC)
    offsets = (
        list(remind_offsets_hours)
        if remind_offsets_hours is not None
        else list(DEFAULT_REMIND_OFFSETS_HOURS)
    )
    sched = _ensure_utc(scheduled_at)
    if interview_id is not None:
        row = await session.get(InterviewEventRow, interview_id)
        if row is not None and row.user_id == user_id:
            row.company = company.strip()
            row.role_title = role_title.strip()
            row.scheduled_at = sched
            row.round = round.strip() if round else None
            row.status = status.value
            row.notes = notes.strip() if notes else None
            row.remind_offsets_hours = offsets
            row.updated_at = now
            await session.flush()
            return _interview_view(row)
    row = InterviewEventRow(
        id=interview_id or uuid4(),
        user_id=user_id,
        company=company.strip(),
        role_title=role_title.strip(),
        scheduled_at=sched,
        round=round.strip() if round else None,
        status=status.value,
        notes=notes.strip() if notes else None,
        remind_offsets_hours=offsets,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    await session.flush()
    return _interview_view(row)


async def patch_interview(
    session: AsyncSession,
    interview_id: UUID,
    *,
    user_id: str = DEFAULT_USER_ID,
    **fields: object,
) -> InterviewEventView:
    row = await session.get(InterviewEventRow, interview_id)
    if row is None or row.user_id != user_id:
        raise KeyError(f"interview not found: {interview_id}")
    now = datetime.now(UTC)
    if "company" in fields and fields["company"] is not None:
        row.company = str(fields["company"]).strip()
    if "role_title" in fields and fields["role_title"] is not None:
        row.role_title = str(fields["role_title"]).strip()
    if "scheduled_at" in fields and fields["scheduled_at"] is not None:
        row.scheduled_at = _ensure_utc(fields["scheduled_at"])  # type: ignore[arg-type]
    if "round" in fields:
        r = fields["round"]
        row.round = str(r).strip() if r else None
    if "status" in fields and fields["status"] is not None:
        st = fields["status"]
        row.status = st.value if isinstance(st, InterviewStatus) else str(st)
    if "notes" in fields:
        n = fields["notes"]
        row.notes = str(n).strip() if n else None
    if "remind_offsets_hours" in fields and fields["remind_offsets_hours"] is not None:
        raw = fields["remind_offsets_hours"]
        if isinstance(raw, (list, tuple, set)):
            row.remind_offsets_hours = [int(x) for x in raw]
        else:
            raise TypeError("remind_offsets_hours must be a sequence of ints")
    row.updated_at = now
    await session.flush()
    return _interview_view(row)


async def update_interview_status(
    session: AsyncSession,
    interview_id: UUID,
    status: InterviewStatus,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> InterviewEventView:
    row = await session.get(InterviewEventRow, interview_id)
    if row is None or row.user_id != user_id:
        raise KeyError(f"interview not found: {interview_id}")
    row.status = status.value
    row.updated_at = datetime.now(UTC)
    await session.flush()
    return _interview_view(row)


async def delete_interview(
    session: AsyncSession,
    interview_id: UUID,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> None:
    row = await session.get(InterviewEventRow, interview_id)
    if row is None or row.user_id != user_id:
        raise KeyError(f"interview not found: {interview_id}")
    await session.delete(row)


async def list_due_interview_reminders(
    session: AsyncSession,
    now: datetime,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> list[DueInterviewReminder]:
    now_utc = _ensure_utc(now)
    stale = timedelta(hours=STALE_REMINDER_HOURS)
    stmt = (
        select(InterviewEventRow)
        .where(InterviewEventRow.user_id == user_id)
        .where(InterviewEventRow.status == InterviewStatus.SCHEDULED.value)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    due: list[DueInterviewReminder] = []
    for row in rows:
        offsets = row.remind_offsets_hours
        if not isinstance(offsets, list) or not offsets:
            offsets = list(DEFAULT_REMIND_OFFSETS_HOURS)
        scheduled = _ensure_utc(row.scheduled_at)
        last = _ensure_utc(row.last_reminded_at) if row.last_reminded_at else None
        for offset in offsets:
            offset_h = int(offset)
            fire_at = scheduled + timedelta(hours=offset_h)
            if fire_at > now_utc:
                continue
            if now_utc > fire_at + stale:
                continue
            if last is not None and last >= fire_at:
                continue
            due.append(
                DueInterviewReminder(
                    interview_id=row.id,
                    company=row.company,
                    role_title=row.role_title,
                    scheduled_at=scheduled,
                    round=row.round,
                    offset_hours=offset_h,
                    fire_at=fire_at,
                )
            )
    due.sort(key=lambda r: (r.fire_at, r.interview_id, r.offset_hours))
    return due


async def mark_interview_reminded(
    session: AsyncSession,
    interview_id: UUID,
    *,
    at: datetime | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> InterviewEventView:
    row = await session.get(InterviewEventRow, interview_id)
    if row is None or row.user_id != user_id:
        raise KeyError(f"interview not found: {interview_id}")
    row.last_reminded_at = _ensure_utc(at or datetime.now(UTC))
    row.updated_at = datetime.now(UTC)
    await session.flush()
    return _interview_view(row)


async def get_interview_ramp_prefs(
    session: AsyncSession,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> InterviewRampPrefs:
    from gotit.db.ops.memory import list_memory

    rows = await list_memory(
        session, user_id=user_id, kind=KIND_INTERVIEW_RAMP_PREFS, limit=1
    )
    if not rows:
        return default_interview_ramp_prefs()
    return _ramp_prefs_from_content(dict(rows[0].content or {}))


async def put_interview_ramp_prefs(
    session: AsyncSession,
    prefs: InterviewRampPrefs,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> InterviewRampPrefs:
    from gotit.db.ops.memory import add_memory

    cleaned = InterviewRampPrefs.model_validate(prefs.model_dump(mode="json"))
    stmt = (
        select(MemoryEntryRow)
        .where(
            MemoryEntryRow.user_id == user_id,
            MemoryEntryRow.kind == KIND_INTERVIEW_RAMP_PREFS,
        )
        .order_by(MemoryEntryRow.created_at.desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    payload = cleaned.model_dump(mode="json")
    if row is None:
        await add_memory(
            session,
            user_id=user_id,
            layer="long",
            kind=KIND_INTERVIEW_RAMP_PREFS,
            content=payload,
        )
    else:
        row.content = payload
        await session.flush()
    return cleaned


async def _primary_project(
    session: AsyncSession, *, user_id: str
) -> tuple[UUID | None, str | None]:
    from gotit.db.ops.project import list_projects

    projects = await list_projects(session, user_id=user_id, include_archived=False)
    if not projects:
        return None, None
    name = (projects[0].name or "").strip() or None
    return projects[0].id, name


def _hours_until(scheduled: datetime, now: datetime) -> float:
    return (scheduled - now).total_seconds() / 3600.0


async def list_upcoming_interviews(
    session: AsyncSession,
    now: datetime,
    *,
    user_id: str = DEFAULT_USER_ID,
    within_hours: float = UPCOMING_WITHIN_HOURS,
) -> list[InterviewUpcoming]:
    """Scheduled interviews in the next ``within_hours`` with ramp metadata."""
    now_utc = _ensure_utc(now)
    horizon = now_utc + timedelta(hours=within_hours)
    stmt = (
        select(InterviewEventRow)
        .where(InterviewEventRow.user_id == user_id)
        .where(InterviewEventRow.status == InterviewStatus.SCHEDULED.value)
        .where(InterviewEventRow.scheduled_at >= now_utc)
        .where(InterviewEventRow.scheduled_at <= horizon)
        .order_by(InterviewEventRow.scheduled_at.asc())
    )
    rows = list((await session.execute(stmt)).scalars().all())
    project_id, project_name = await _primary_project(session, user_id=user_id)
    out: list[InterviewUpcoming] = []
    for row in rows:
        scheduled = _ensure_utc(row.scheduled_at)
        hours = _hours_until(scheduled, now_utc)
        tier = ramp_tier(hours)
        out.append(
            InterviewUpcoming(
                interview_id=row.id,
                company=row.company,
                role_title=row.role_title,
                scheduled_at=scheduled,
                round=row.round,
                hours_until=round(hours, 2),
                ramp_tier=tier,
                tier_hint=tier_hint_zh(tier),
                suggest_action=suggest_action(round=row.round, project_name=project_name),
                project_name=project_name,
                project_id=project_id,
            )
        )
    return out


async def list_interview_ramp_nudges(
    session: AsyncSession,
    now: datetime,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> list[InterviewRampNudge]:
    """At most one deliverable light/warm nudge (prefs + cooldown + weekly cap)."""
    prefs = await get_interview_ramp_prefs(session, user_id=user_id)
    if not prefs.enabled or prefs.max_nudges_per_week <= 0:
        return []

    now_utc = _ensure_utc(now)
    upcoming = await list_upcoming_interviews(session, now_utc, user_id=user_id)
    deliverable = [u for u in upcoming if u.ramp_tier in DELIVERABLE_TIERS]
    if not deliverable:
        return []

    # Weekly cap: count interviews nudged in the last 7 days.
    week_ago = now_utc - timedelta(days=7)
    stmt = (
        select(InterviewEventRow)
        .where(InterviewEventRow.user_id == user_id)
        .where(InterviewEventRow.last_ramp_nudge_at.is_not(None))
        .where(InterviewEventRow.last_ramp_nudge_at >= week_ago)
    )
    recent = list((await session.execute(stmt)).scalars().all())
    if len(recent) >= prefs.max_nudges_per_week:
        return []

    cooldown = timedelta(hours=RAMP_NUDGE_COOLDOWN_HOURS)
    by_id = {
        r.id: r
        for r in (
            await session.execute(
                select(InterviewEventRow).where(
                    InterviewEventRow.id.in_([u.interview_id for u in deliverable])
                )
            )
        ).scalars()
    }

    for u in deliverable:
        row = by_id.get(u.interview_id)
        if row is None:
            continue
        last = _ensure_utc(row.last_ramp_nudge_at) if row.last_ramp_nudge_at else None
        if last is not None and now_utc < last + cooldown:
            continue
        # Narrow type: deliverable tiers are light|warm only.
        tier = u.ramp_tier
        if tier not in ("light", "warm"):
            continue
        return [
            InterviewRampNudge(
                interview_id=u.interview_id,
                company=u.company,
                role_title=u.role_title,
                scheduled_at=u.scheduled_at,
                round=u.round,
                hours_until=u.hours_until,
                ramp_tier=tier,
                suggest_action=u.suggest_action,
                project_name=u.project_name,
                project_id=u.project_id,
                tier_hint=u.tier_hint,
            )
        ]
    return []


async def mark_interview_ramp_nudged(
    session: AsyncSession,
    interview_id: UUID,
    *,
    at: datetime | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> InterviewEventView:
    row = await session.get(InterviewEventRow, interview_id)
    if row is None or row.user_id != user_id:
        raise KeyError(f"interview not found: {interview_id}")
    row.last_ramp_nudge_at = _ensure_utc(at or datetime.now(UTC))
    row.updated_at = datetime.now(UTC)
    await session.flush()
    return _interview_view(row)
