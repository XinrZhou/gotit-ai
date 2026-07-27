"""Shared day/plan/note/claim operations used by REST and MCP."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from gotit.core.models import (
    Claim,
    ChatMessageView,
    DayNoteView,
    DayPlanView,
    MasteryStatus,
    PlanItemSource,
    PlanItemStatus,
    PlanItemView,
    TodayView,
)
from gotit.db.models import (
    ChatMessageRow,
    ClaimRow,
    DayNoteRow,
    LearningDayRow,
    PlanItemRow,
)

DEFAULT_USER_ID = "local"
EXCERPT_LEN = 240


def _excerpt(body: str, limit: int = EXCERPT_LEN) -> str:
    text = body.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _plan_item_view(row: PlanItemRow) -> PlanItemView:
    return PlanItemView(
        id=row.id,
        title=row.title,
        source=PlanItemSource(row.source),
        status=PlanItemStatus(row.status),
        claim_id=row.claim_id,
        sort_order=row.sort_order,
        due_at=row.due_at,
    )


def _note_view(row: DayNoteRow, *, full_body: bool = False) -> DayNoteView:
    claim_ids = [UUID(str(c)) for c in (row.claim_ids or [])]
    body = row.body if full_body else ""
    return DayNoteView(
        id=row.id,
        title=row.title,
        body=body if full_body else _excerpt(row.body),
        excerpt=_excerpt(row.body),
        tags=list(row.tags or []),
        claim_ids=claim_ids,
        created_at=row.created_at or datetime.now(UTC),
    )


def _claim_view(row: ClaimRow) -> Claim:
    return Claim(
        id=row.id,
        text=row.text,
        source_excerpt=row.source_excerpt,
        status=MasteryStatus(row.status),
        source_note_id=row.source_note_id,
        next_review_at=row.next_review_at,
    )


async def ensure_day(
    session: AsyncSession,
    day: date,
    *,
    user_id: str = DEFAULT_USER_ID,
    timezone_name: str = "UTC",
) -> LearningDayRow:
    stmt: Select[tuple[LearningDayRow]] = (
        select(LearningDayRow)
        .where(LearningDayRow.user_id == user_id, LearningDayRow.day == day)
        .options(selectinload(LearningDayRow.plan_items), selectinload(LearningDayRow.notes))
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return existing
    row = LearningDayRow(id=uuid4(), user_id=user_id, day=day, timezone=timezone_name)
    session.add(row)
    await session.flush()
    loaded = (await session.execute(stmt)).scalar_one()
    return loaded


async def get_plan(
    session: AsyncSession,
    day: date,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> DayPlanView:
    learning_day = await ensure_day(session, day, user_id=user_id)
    items = sorted(learning_day.plan_items, key=lambda i: (i.sort_order, str(i.id)))
    return DayPlanView(date=day, user_id=user_id, items=[_plan_item_view(i) for i in items])


async def upsert_plan_item(
    session: AsyncSession,
    day: date,
    *,
    title: str,
    user_id: str = DEFAULT_USER_ID,
    item_id: UUID | None = None,
    source: PlanItemSource = PlanItemSource.MANUAL,
    status: PlanItemStatus = PlanItemStatus.PLANNED,
    claim_id: UUID | None = None,
    sort_order: int | None = None,
    due_at: date | None = None,
) -> PlanItemView:
    learning_day = await ensure_day(session, day, user_id=user_id)
    if item_id is not None:
        row = await session.get(PlanItemRow, item_id)
        if row is None or row.day_id != learning_day.id:
            raise KeyError(f"plan item not found: {item_id}")
        row.title = title.strip()
        row.source = source.value
        row.status = status.value
        row.claim_id = claim_id
        if sort_order is not None:
            row.sort_order = sort_order
        row.due_at = due_at
    else:
        order = sort_order if sort_order is not None else len(learning_day.plan_items)
        row = PlanItemRow(
            id=uuid4(),
            day_id=learning_day.id,
            title=title.strip(),
            source=source.value,
            status=status.value,
            claim_id=claim_id,
            sort_order=order,
            due_at=due_at,
        )
        session.add(row)
    await session.flush()
    return _plan_item_view(row)


async def update_plan_item(
    session: AsyncSession,
    item_id: UUID,
    *,
    title: str | None = None,
    status: PlanItemStatus | None = None,
    sort_order: int | None = None,
    due_at: date | None = None,
    defer_to: date | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> PlanItemView:
    row = await session.get(PlanItemRow, item_id)
    if row is None:
        raise KeyError(f"plan item not found: {item_id}")
    day_row = await session.get(LearningDayRow, row.day_id)
    if day_row is None or day_row.user_id != user_id:
        raise KeyError(f"plan item not found: {item_id}")
    if title is not None:
        row.title = title.strip()
    if status is not None:
        row.status = status.value
    if sort_order is not None:
        row.sort_order = sort_order
    if due_at is not None:
        row.due_at = due_at
    if defer_to is not None:
        row.status = PlanItemStatus.DEFERRED.value
        row.due_at = defer_to
        # Move item to the deferred day so it appears on that plan.
        target = await ensure_day(session, defer_to, user_id=user_id)
        row.day_id = target.id
    await session.flush()
    return _plan_item_view(row)


async def delete_plan_item(
    session: AsyncSession,
    item_id: UUID,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> None:
    row = await session.get(PlanItemRow, item_id)
    if row is None:
        raise KeyError(f"plan item not found: {item_id}")
    day_row = await session.get(LearningDayRow, row.day_id)
    if day_row is None or day_row.user_id != user_id:
        raise KeyError(f"plan item not found: {item_id}")
    await session.delete(row)
    await session.flush()


async def list_due_claims(
    session: AsyncSession,
    as_of: date,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> list[ClaimRow]:
    stmt = select(ClaimRow).where(
        ClaimRow.user_id == user_id,
        ClaimRow.status.in_([MasteryStatus.QUEUED.value, MasteryStatus.NOT_YET.value]),
        or_(ClaimRow.next_review_at.is_(None), ClaimRow.next_review_at <= as_of),
    )
    return list((await session.execute(stmt)).scalars().all())


async def fill_today_from_queue(
    session: AsyncSession,
    day: date,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> DayPlanView:
    learning_day = await ensure_day(session, day, user_id=user_id)
    existing_claim_ids = {i.claim_id for i in learning_day.plan_items if i.claim_id is not None}
    due = await list_due_claims(session, day, user_id=user_id)
    next_order = max((i.sort_order for i in learning_day.plan_items), default=-1) + 1
    for claim in due:
        if claim.id in existing_claim_ids:
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


async def add_note(
    session: AsyncSession,
    day: date,
    body: str,
    *,
    title: str | None = None,
    tags: list[str] | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> DayNoteView:
    learning_day = await ensure_day(session, day, user_id=user_id)
    row = DayNoteRow(
        id=uuid4(),
        day_id=learning_day.id,
        title=title,
        body=body.strip(),
        tags=list(tags or []),
        claim_ids=[],
        created_at=datetime.now(UTC),
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
    learning_day = await ensure_day(session, day, user_id=user_id)
    notes = sorted(
        learning_day.notes,
        key=lambda n: n.created_at or datetime.min.replace(tzinfo=UTC),
    )
    return [_note_view(n, full_body=full_body) for n in notes]


def stub_extract_claim(material: str, *, source_note_id: UUID | None = None) -> Claim:
    text = material.strip()[:500]
    return Claim(
        id=uuid4(),
        text=text,
        source_excerpt=material[:200],
        status=MasteryStatus.NOT_YET,
        source_note_id=source_note_id,
        next_review_at=None,
    )


async def ingest_note(
    session: AsyncSession,
    note_id: UUID,
    *,
    user_id: str = DEFAULT_USER_ID,
    add_plan_item: bool = True,
) -> dict[str, object]:
    note = await session.get(DayNoteRow, note_id)
    if note is None:
        raise KeyError(f"note not found: {note_id}")
    day_row = await session.get(LearningDayRow, note.day_id)
    if day_row is None or day_row.user_id != user_id:
        raise KeyError(f"note not found: {note_id}")

    claim = stub_extract_claim(note.body, source_note_id=note.id)
    claim_row = ClaimRow(
        id=claim.id,
        user_id=user_id,
        text=claim.text,
        source_excerpt=claim.source_excerpt,
        status=claim.status.value,
        source_note_id=note.id,
        next_review_at=None,
    )
    session.add(claim_row)
    ids = [UUID(str(c)) for c in (note.claim_ids or [])]
    ids.append(claim.id)
    note.claim_ids = [str(c) for c in ids]

    plan_item: PlanItemView | None = None
    if add_plan_item:
        plan_item = await upsert_plan_item(
            session,
            day_row.day,
            title=claim.text[:500],
            user_id=user_id,
            source=PlanItemSource.MANUAL,
            claim_id=claim.id,
        )
    await session.flush()
    return {
        "note_id": str(note.id),
        "claims": [claim.model_dump(mode="json")],
        "plan_item": plan_item.model_dump(mode="json") if plan_item else None,
        "note": "stub: claim extraction not wired yet",
    }


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


async def list_chat_messages(
    session: AsyncSession,
    plan_item_id: UUID,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> list[ChatMessageView]:
    row = await session.get(PlanItemRow, plan_item_id)
    if row is None:
        raise KeyError(f"plan item not found: {plan_item_id}")
    day_row = await session.get(LearningDayRow, row.day_id)
    if day_row is None or day_row.user_id != user_id:
        raise KeyError(f"plan item not found: {plan_item_id}")
    stmt = (
        select(ChatMessageRow)
        .where(ChatMessageRow.plan_item_id == plan_item_id)
        .order_by(ChatMessageRow.created_at, ChatMessageRow.id)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    return [
        ChatMessageView(
            id=r.id,
            plan_item_id=r.plan_item_id,
            role=r.role,
            text=r.text,
            created_at=r.created_at or datetime.now(UTC),
        )
        for r in rows
    ]


async def add_chat_message(
    session: AsyncSession,
    plan_item_id: UUID,
    role: str,
    text: str,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> ChatMessageView:
    row = await session.get(PlanItemRow, plan_item_id)
    if row is None:
        raise KeyError(f"plan item not found: {plan_item_id}")
    day_row = await session.get(LearningDayRow, row.day_id)
    if day_row is None or day_row.user_id != user_id:
        raise KeyError(f"plan item not found: {plan_item_id}")
    msg = ChatMessageRow(
        id=uuid4(),
        plan_item_id=plan_item_id,
        role=role,
        text=text.strip(),
    )
    session.add(msg)
    await session.flush()
    return ChatMessageView(
        id=msg.id,
        plan_item_id=plan_item_id,
        role=role,
        text=msg.text,
        created_at=msg.created_at or datetime.now(UTC),
    )


async def get_today(
    session: AsyncSession,
    day: date | None = None,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> TodayView:
    target = day or date.today()
    plan = await get_plan(session, target, user_id=user_id)
    notes = await list_notes(session, target, user_id=user_id, full_body=False)
    due_rows = await list_due_claims(session, target, user_id=user_id)
    return TodayView(
        date=target,
        plan=plan,
        notes=notes,
        due_claims=[_claim_view(r) for r in due_rows],
    )


async def apply_examine_result(
    session: AsyncSession,
    claim_id: UUID,
    *,
    passed: bool,
    user_id: str = DEFAULT_USER_ID,
    as_of: date | None = None,
) -> dict[str, object]:
    """Writeback claim + linked plan items after an examine attempt (stub-friendly)."""
    today = as_of or date.today()
    claim = await session.get(ClaimRow, claim_id)
    if claim is None or claim.user_id != user_id:
        raise KeyError(f"claim not found: {claim_id}")

    stmt = select(PlanItemRow).where(PlanItemRow.claim_id == claim_id)
    items = list((await session.execute(stmt)).scalars().all())

    if passed:
        claim.status = MasteryStatus.MASTERED.value
        claim.next_review_at = None
        for item in items:
            item.status = PlanItemStatus.VERIFIED.value
    else:
        claim.status = MasteryStatus.QUEUED.value
        claim.next_review_at = today + timedelta(days=1)
        for item in items:
            item.status = PlanItemStatus.FAILED.value

    await session.flush()
    return {
        "claim": _claim_view(claim).model_dump(mode="json"),
        "plan_items": [_plan_item_view(i).model_dump(mode="json") for i in items],
        "passed": passed,
    }
