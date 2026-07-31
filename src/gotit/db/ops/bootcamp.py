"""First-pass bootcamp — empty-library guide state (memory-backed)."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from gotit.core.models import BootcampView
from gotit.db.models import ClaimRow, DayNoteRow, LearningDayRow, MemoryEntryRow
from gotit.db.ops._common import DEFAULT_USER_ID

KIND_BOOTCAMP = "bootcamp"
# Almost-empty: no claims and at most this many notes.
NOTE_FEW = 2

BootcampStatus = Literal["none", "in_progress", "done", "skipped"]
_STORED = frozenset({"in_progress", "done", "skipped"})


def _status_from_content(content: dict[str, Any] | None) -> BootcampStatus:
    raw = (content or {}).get("status")
    if raw == "in_progress":
        return "in_progress"
    if raw == "done":
        return "done"
    if raw == "skipped":
        return "skipped"
    return "none"


async def get_bootcamp_status(
    session: AsyncSession,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> BootcampStatus:
    from gotit.db.ops.memory import list_memory

    rows = await list_memory(session, user_id=user_id, kind=KIND_BOOTCAMP, limit=1)
    if not rows:
        return "none"
    return _status_from_content(dict(rows[0].content or {}))


async def put_bootcamp_status(
    session: AsyncSession,
    status: Literal["in_progress", "done", "skipped"],
    *,
    user_id: str = DEFAULT_USER_ID,
) -> BootcampStatus:
    from gotit.db.ops.memory import add_memory

    if status not in _STORED:
        raise ValueError(f"invalid bootcamp status: {status}")
    stmt = (
        select(MemoryEntryRow)
        .where(
            MemoryEntryRow.user_id == user_id,
            MemoryEntryRow.kind == KIND_BOOTCAMP,
        )
        .order_by(MemoryEntryRow.created_at.desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    payload = {"status": status}
    if row is None:
        await add_memory(
            session,
            user_id=user_id,
            layer="long",
            kind=KIND_BOOTCAMP,
            content=payload,
        )
    else:
        row.content = payload
        await session.flush()
    return status


async def _count_claims(
    session: AsyncSession, *, user_id: str
) -> int:
    stmt = select(func.count()).select_from(ClaimRow).where(ClaimRow.user_id == user_id)
    return int((await session.execute(stmt)).scalar_one())


async def _count_notes(
    session: AsyncSession, *, user_id: str
) -> int:
    stmt = (
        select(func.count())
        .select_from(DayNoteRow)
        .join(LearningDayRow, DayNoteRow.day_id == LearningDayRow.id)
        .where(LearningDayRow.user_id == user_id)
    )
    return int((await session.execute(stmt)).scalar_one())


async def _first_claim(
    session: AsyncSession, *, user_id: str
) -> tuple[UUID, str] | None:
    stmt = (
        select(ClaimRow).where(ClaimRow.user_id == user_id).order_by(ClaimRow.id.asc()).limit(1)
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        return None
    return row.id, (row.text or "").strip()


async def _latest_gate(
    session: AsyncSession, *, user_id: str, claim_id: UUID | None
) -> Literal["passed", "almost", "owe_next"] | None:
    from gotit.db.ops.memory import list_trajectory

    entries = await list_trajectory(
        session, user_id=user_id, claim_id=claim_id, limit=5
    )
    if not entries and claim_id is not None:
        entries = await list_trajectory(session, user_id=user_id, limit=5)
    for e in entries:
        raw = e.content.get("gate_verdict") or e.content.get("verdict")
        if raw == "passed":
            return "passed"
        if raw == "almost":
            return "almost"
        if raw == "owe_next":
            return "owe_next"
    return None


async def resolve_bootcamp(
    session: AsyncSession,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> BootcampView:
    """Compute bootcamp show/step for SessionStart (empty library only)."""
    status = await get_bootcamp_status(session, user_id=user_id)
    claim_count = await _count_claims(session, user_id=user_id)
    note_count = await _count_notes(session, user_id=user_id)

    if status in {"done", "skipped"}:
        return BootcampView(
            status=status,
            show=False,
            step=None,
            claim_count=claim_count,
            note_count=note_count,
        )

    almost_empty = claim_count == 0 and note_count <= NOTE_FEW
    if status != "in_progress" and not almost_empty:
        # Has real data and never started — do not nag.
        return BootcampView(
            status="none",
            show=False,
            step=None,
            claim_count=claim_count,
            note_count=note_count,
        )

    first = await _first_claim(session, user_id=user_id)
    claim_id = first[0] if first else None
    claim_text = first[1] if first else None
    gate = await _latest_gate(session, user_id=user_id, claim_id=claim_id)

    if gate is not None and claim_id is not None:
        step: Literal["ingest", "verify", "celebrate"] = "celebrate"
    elif claim_count > 0 and claim_id is not None:
        step = "verify"
    else:
        step = "ingest"

    return BootcampView(
        status=status if status == "in_progress" else "none",
        show=True,
        step=step,
        claim_count=claim_count,
        note_count=note_count,
        claim_id=claim_id,
        claim_text=claim_text,
        gate_verdict=gate,
    )
