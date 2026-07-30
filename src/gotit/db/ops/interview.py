"""Scheduled real-world interview events (companion-os P3d)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gotit.core.models import (
    DEFAULT_REMIND_OFFSETS_HOURS,
    DueInterviewReminder,
    InterviewEventView,
    InterviewStatus,
)
from gotit.db.models import InterviewEventRow
from gotit.db.ops._common import DEFAULT_USER_ID

STALE_REMINDER_HOURS = 6


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
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


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
