"""Learning-day, plan, chat-message, and today-aggregate operations."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Select, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from gotit.core.models import (
    ChatMessageView,
    DayPlanView,
    MasteryStatus,
    PlanItemSource,
    PlanItemStatus,
    PlanItemView,
    TodayView,
)
from gotit.db.models import ChatMessageRow, ClaimRow, LearningDayRow, PlanItemRow
from gotit.db.ops._common import DEFAULT_USER_ID, _claim_view, _plan_item_view
from gotit.db.ops.note import list_notes


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
    try:
        await session.flush()
    except IntegrityError:
        # concurrent ensure_day on the same (user, day) won the race; reuse it.
        await session.rollback()
        loaded = (await session.execute(stmt)).scalar_one()
        return loaded
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
    claim_ids = [i.claim_id for i in items if i.claim_id is not None]
    topic_map: dict[UUID, str | None] = {}
    if claim_ids:
        stmt = select(ClaimRow).where(ClaimRow.id.in_(claim_ids))
        rows = list((await session.execute(stmt)).scalars().all())
        topic_map = {r.id: r.topic for r in rows}
    return DayPlanView(
        date=day,
        user_id=user_id,
        items=[
            _plan_item_view(i, topic=topic_map.get(i.claim_id) if i.claim_id else None)
            for i in items
        ],
    )


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
    project_id: UUID | None = None,
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
        row.project_id = project_id
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
            project_id=project_id,
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
        ClaimRow.status.in_(
            [
                MasteryStatus.QUEUED.value,
                MasteryStatus.NOT_YET.value,
                MasteryStatus.IN_PROGRESS.value,
            ]
        ),
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
