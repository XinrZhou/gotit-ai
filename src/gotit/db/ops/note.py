"""Note CRUD, claim extraction/ingest, and note/project claim listing."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from gotit.core.models import (
    Claim,
    DayNoteView,
    DayPlanView,
    MasteryStatus,
    PlanItemSource,
    PlanItemStatus,
    PlanItemView,
)
from gotit.db.models import ClaimRow, DayNoteRow, LearningDayRow, PlanItemRow
from gotit.db.ops._common import DEFAULT_USER_ID, _claim_view, _note_view


def _strip_html(raw: str) -> str:
    """Strip HTML tags and unescape entities (notes are stored as HTML)."""
    import html
    import re

    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def stub_extract_claim(material: str, *, source_note_id: UUID | None = None) -> Claim:
    plain = _strip_html(material)
    text = plain[:500]
    return Claim(
        id=uuid4(),
        text=text,
        source_excerpt=plain[:200],
        status=MasteryStatus.NOT_YET,
        source_note_id=source_note_id,
        next_review_at=None,
        topic=None,
        tags=[],
    )


async def add_note(
    session: AsyncSession,
    day: date,
    body: str,
    *,
    title: str | None = None,
    tags: list[str] | None = None,
    user_id: str = DEFAULT_USER_ID,
    project_id: UUID | None = None,
) -> DayNoteView:
    from gotit.db.ops.day import ensure_day

    learning_day = await ensure_day(session, day, user_id=user_id)
    row = DayNoteRow(
        id=uuid4(),
        day_id=learning_day.id,
        title=title,
        body=body.strip(),
        tags=list(tags or []),
        claim_ids=[],
        created_at=datetime.now(UTC),
        project_id=project_id,
    )
    session.add(row)
    await session.flush()
    return _note_view(row, full_body=True)


async def list_notes(
    session: AsyncSession,
    day: date,
    *,
    user_id: str = DEFAULT_USER_ID,
    full_body: bool = False,
) -> list[DayNoteView]:
    from gotit.db.ops.day import ensure_day

    learning_day = await ensure_day(session, day, user_id=user_id)
    notes = sorted(
        learning_day.notes,
        key=lambda n: n.created_at or datetime.min.replace(tzinfo=UTC),
    )
    return [_note_view(n, full_body=full_body) for n in notes]


async def list_all_notes(
    session: AsyncSession,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> list[DayNoteView]:
    """All notes across days for a user, newest first (with day label)."""
    stmt = (
        select(DayNoteRow)
        .join(LearningDayRow, DayNoteRow.day_id == LearningDayRow.id)
        .where(LearningDayRow.user_id == user_id)
        .options(selectinload(DayNoteRow.learning_day))
        .order_by(DayNoteRow.created_at.desc(), DayNoteRow.id.desc())
    )
    rows = list((await session.execute(stmt)).scalars().all())
    return [_note_view(r, full_body=False) for r in rows]


async def get_note(
    session: AsyncSession,
    note_id: UUID,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> DayNoteView:
    note = await session.get(DayNoteRow, note_id)
    if note is None:
        raise KeyError(f"note not found: {note_id}")
    day_row = await session.get(LearningDayRow, note.day_id)
    if day_row is None or day_row.user_id != user_id:
        raise KeyError(f"note not found: {note_id}")
    return _note_view(note, full_body=True)


async def delete_note(
    session: AsyncSession,
    note_id: UUID,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> None:
    note = await session.get(DayNoteRow, note_id)
    if note is None:
        raise KeyError(f"note not found: {note_id}")
    day_row = await session.get(LearningDayRow, note.day_id)
    if day_row is None or day_row.user_id != user_id:
        raise KeyError(f"note not found: {note_id}")
    await session.delete(note)
    await session.flush()


async def delete_notes(
    session: AsyncSession,
    note_ids: list[UUID],
    *,
    user_id: str = DEFAULT_USER_ID,
) -> int:
    """Delete many notes owned by ``user_id``. Skips unknown ids. Returns deleted count."""
    deleted = 0
    for note_id in note_ids:
        try:
            await delete_note(session, note_id, user_id=user_id)
            deleted += 1
        except KeyError:
            continue
    return deleted


async def ingest_note(
    session: AsyncSession,
    note_id: UUID,
    *,
    claims: list[Claim] | None = None,
    user_id: str = DEFAULT_USER_ID,
    add_plan_item: bool = True,
) -> dict[str, object]:
    """Persist claims for a note. `claims` defaults to a stub extraction."""
    from gotit.db.ops.day import upsert_plan_item

    note = await session.get(DayNoteRow, note_id)
    if note is None:
        raise KeyError(f"note not found: {note_id}")
    day_row = await session.get(LearningDayRow, note.day_id)
    if day_row is None or day_row.user_id != user_id:
        raise KeyError(f"note not found: {note_id}")

    if claims is None:
        claims = [stub_extract_claim(note.body, source_note_id=note.id)]

    persisted: list[Claim] = []
    for claim in claims:
        claim.project_id = note.project_id
        claim_row = ClaimRow(
            id=claim.id,
            user_id=user_id,
            text=claim.text,
            source_excerpt=claim.source_excerpt,
            status=claim.status.value,
            source_note_id=note.id,
            next_review_at=claim.next_review_at,
            topic=claim.topic,
            tags=list(claim.tags),
            project_id=note.project_id,
        )
        session.add(claim_row)
        persisted.append(claim)

    ids = [UUID(str(c)) for c in (note.claim_ids or [])]
    for claim in persisted:
        ids.append(claim.id)
    note.claim_ids = [str(c) for c in ids]

    plan_items: list[PlanItemView] = []
    if add_plan_item:
        for claim in persisted:
            plan_items.append(
                await upsert_plan_item(
                    session,
                    day_row.day,
                    title=claim.text[:500],
                    user_id=user_id,
                    source=PlanItemSource.MANUAL,
                    claim_id=claim.id,
                    project_id=note.project_id,
                )
            )
    await session.flush()
    return {
        "note_id": str(note.id),
        "claims": [c.model_dump(mode="json") for c in persisted],
        "plan_items": [p.model_dump(mode="json") for p in plan_items],
    }


async def curate_claims(
    session: AsyncSession,
    day: date,
    *,
    claim_texts: list[str],
    user_id: str = DEFAULT_USER_ID,
) -> DayPlanView:
    """Add plan items for recommended claims (matched by text) for the day."""
    from gotit.db.ops.day import ensure_day, get_plan

    learning_day = await ensure_day(session, day, user_id=user_id)
    existing_claim_ids = {i.claim_id for i in learning_day.plan_items if i.claim_id is not None}
    next_order = max((i.sort_order for i in learning_day.plan_items), default=-1) + 1
    for text in claim_texts:
        stmt = select(ClaimRow).where(
            ClaimRow.user_id == user_id, ClaimRow.text == text
        ).limit(1)
        claim = (await session.execute(stmt)).scalar_one_or_none()
        if claim is None or claim.id in existing_claim_ids:
            continue
        session.add(
            PlanItemRow(
                id=uuid4(),
                day_id=learning_day.id,
                title=claim.text[:500],
                source=PlanItemSource.QUEUE.value,
                status=PlanItemStatus.PLANNED.value,
                claim_id=claim.id,
                sort_order=next_order,
                due_at=day,
            )
        )
        next_order += 1
    await session.flush()
    session.expire_all()
    return await get_plan(session, day, user_id=user_id)


async def list_note_claims(
    session: AsyncSession,
    note_id: UUID,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> list[Claim]:
    """All not-yet-mastered claims sourced from a given note (any day).

    Ordered by the note's `claim_ids` array (extraction order).
    """
    note = await session.get(DayNoteRow, note_id)
    if note is None or (note.claim_ids or []) == []:
        return []
    ordered_ids = [UUID(str(c)) for c in note.claim_ids]
    stmt = select(ClaimRow).where(
        ClaimRow.id.in_(ordered_ids),
        ClaimRow.user_id == user_id,
        ClaimRow.status != MasteryStatus.MASTERED.value,
    )
    rows = list((await session.execute(stmt)).scalars().all())
    by_id = {r.id: r for r in rows}
    return [_claim_view(by_id[cid]) for cid in ordered_ids if cid in by_id]


async def list_project_notes(
    session: AsyncSession,
    project_id: UUID,
    *,
    user_id: str = DEFAULT_USER_ID,
    full_body: bool = False,
) -> list[DayNoteView]:
    stmt = (
        select(DayNoteRow)
        .join(LearningDayRow, DayNoteRow.day_id == LearningDayRow.id)
        .where(DayNoteRow.project_id == project_id, LearningDayRow.user_id == user_id)
        .order_by(DayNoteRow.created_at.desc())
    )
    rows = list((await session.execute(stmt)).scalars().all())
    return [_note_view(r, full_body=full_body) for r in rows]
