"""Learning-day, plan, and today-aggregate operations."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Select, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from gotit.core.models import (
    Claim,
    DayCloseSummary,
    DayPlanView,
    MasteryStatus,
    PlanItemSource,
    PlanItemStatus,
    PlanItemView,
    TodayView,
)
from gotit.core.plan_time import resolve_due_time
from gotit.db.models import ClaimRow, LearningDayRow, PlanItemRow
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
    due_time: str | None = None,
    project_id: UUID | None = None,
) -> PlanItemView:
    learning_day = await ensure_day(session, day, user_id=user_id)
    clean_title = title.strip()
    resolved_time = resolve_due_time(due_time=due_time, title=clean_title)
    if item_id is not None:
        row = await session.get(PlanItemRow, item_id)
        if row is None or row.day_id != learning_day.id:
            raise KeyError(f"plan item not found: {item_id}")
        row.title = clean_title
        row.source = source.value
        row.status = status.value
        row.claim_id = claim_id
        if sort_order is not None:
            row.sort_order = sort_order
        row.due_at = due_at
        if due_time is not None or resolved_time:
            row.due_time = resolved_time
        row.project_id = project_id
    else:
        order = sort_order if sort_order is not None else len(learning_day.plan_items)
        row = PlanItemRow(
            id=uuid4(),
            day_id=learning_day.id,
            title=clean_title,
            source=source.value,
            status=status.value,
            claim_id=claim_id,
            sort_order=order,
            due_at=due_at,
            due_time=resolved_time,
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
    due_time: str | None = None,
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
    if due_time is not None:
        row.due_time = resolve_due_time(due_time=due_time, title=row.title)
    elif title is not None and not row.due_time:
        row.due_time = resolve_due_time(due_time=None, title=row.title)
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
    rows = list((await session.execute(stmt)).scalars().all())
    return await _sort_due_claims(session, rows, as_of=as_of, user_id=user_id)


async def _sort_due_claims(
    session: AsyncSession,
    due: list[ClaimRow],
    *,
    as_of: date,
    user_id: str,
) -> list[ClaimRow]:
    """Rank due: overdue → unmet-depends demote → fail → confuse → id."""
    if not due:
        return due
    from gotit.core.schedule import (
        confuse_weights_from_edges,
        depends_blocked_map,
        due_sort_key,
    )
    from gotit.db.ops.graph import (
        fail_counts_by_claim,
        list_confused_edges,
        list_depends_edges,
        mastered_claim_ids,
    )

    fail_counts = await fail_counts_by_claim(
        session, user_id=user_id, claim_ids=[c.id for c in due]
    )
    edge_rows = await list_confused_edges(session, user_id=user_id, min_weight=1)
    edges = [
        (r.source_claim_id, r.target_claim_id, int(r.weight)) for r in edge_rows
    ]
    weights = confuse_weights_from_edges([c.id for c in due], edges)
    depends_rows = await list_depends_edges(session, user_id=user_id)
    depends_tuples = [
        (r.source_claim_id, r.target_claim_id) for r in depends_rows
    ]
    prereq_ids = list({pre for _, pre in depends_tuples})
    mastered = await mastered_claim_ids(
        session, user_id=user_id, claim_ids=prereq_ids
    )
    blocked = depends_blocked_map(
        [c.id for c in due],
        depends_edges=depends_tuples,
        mastered_ids=mastered,
    )
    return sorted(
        due,
        key=lambda c: due_sort_key(
            as_of=as_of,
            next_review_at=c.next_review_at,
            fail_count=fail_counts.get(c.id, 0),
            confuse_weight=weights.get(c.id, 0),
            depends_blocked=blocked.get(c.id, False),
            claim_id=c.id,
        ),
    )


async def _due_claim_views(
    session: AsyncSession,
    due: list[ClaimRow],
    *,
    as_of: date,
    user_id: str,
) -> list[Claim]:
    """Enrich due rows with reason_code/text for today / MCP surfaces."""
    from gotit.core.schedule import (
        confuse_weights_from_edges,
        explain_due_reason,
        top_confuse_neighbor_ids,
        unmet_depends_prereq_ids,
    )
    from gotit.db.ops.graph import (
        fail_counts_by_claim,
        list_confused_edges,
        list_depends_edges,
        mastered_claim_ids,
    )

    if not due:
        return []
    edge_rows = await list_confused_edges(session, user_id=user_id, min_weight=1)
    edges = [
        (r.source_claim_id, r.target_claim_id, int(r.weight)) for r in edge_rows
    ]
    weights = confuse_weights_from_edges([c.id for c in due], edges)
    fail_counts = await fail_counts_by_claim(
        session, user_id=user_id, claim_ids=[c.id for c in due]
    )
    depends_rows = await list_depends_edges(session, user_id=user_id)
    depends_tuples = [
        (r.source_claim_id, r.target_claim_id) for r in depends_rows
    ]
    prereq_ids = list({pre for _, pre in depends_tuples})
    mastered = await mastered_claim_ids(
        session, user_id=user_id, claim_ids=prereq_ids
    )
    neighbor_by_claim: dict[UUID, UUID | None] = {}
    depends_by_claim: dict[UUID, UUID | None] = {}
    label_ids: set[UUID] = set()
    for c in due:
        tops = top_confuse_neighbor_ids(target_id=c.id, edges=edges, limit=1)
        nid = tops[0] if tops else None
        neighbor_by_claim[c.id] = nid
        if nid is not None:
            label_ids.add(nid)
        unmet = unmet_depends_prereq_ids(
            claim_id=c.id,
            depends_edges=depends_tuples,
            mastered_ids=mastered,
        )
        pid = unmet[0] if unmet else None
        depends_by_claim[c.id] = pid
        if pid is not None:
            label_ids.add(pid)
    labels: dict[UUID, str] = {}
    if label_ids:
        rows = list(
            (
                await session.execute(
                    select(ClaimRow).where(
                        ClaimRow.id.in_(label_ids), ClaimRow.user_id == user_id
                    )
                )
            )
            .scalars()
            .all()
        )
        labels = {r.id: r.text for r in rows}

    from gotit.db.ops.memory import failure_hints_by_claim

    hints = await failure_hints_by_claim(
        session, user_id=user_id, claim_ids=[c.id for c in due]
    )

    out: list[Claim] = []
    for c in due:
        nid = neighbor_by_claim.get(c.id)
        pid = depends_by_claim.get(c.id)
        code, text = explain_due_reason(
            as_of=as_of,
            status=c.status,
            next_review_at=c.next_review_at,
            confuse_weight=weights.get(c.id, 0),
            confuse_neighbor_label=labels.get(nid) if nid else None,
            depends_prereq_label=labels.get(pid) if pid else None,
            fail_count=fail_counts.get(c.id, 0),
        )
        out.append(
            _claim_view(
                c,
                due_reason_code=code,
                due_reason_text=text,
                failure_hint=hints.get(c.id),
            )
        )
    return out


async def fill_today_from_queue(
    session: AsyncSession,
    day: date,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> DayPlanView:
    learning_day = await ensure_day(session, day, user_id=user_id)
    existing_claim_ids = {i.claim_id for i in learning_day.plan_items if i.claim_id is not None}
    # list_due_claims already sorts: overdue → severity → confuse → id
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


async def get_today(
    session: AsyncSession,
    day: date | None = None,
    *,
    user_id: str = DEFAULT_USER_ID,
    now: datetime | None = None,
) -> TodayView:
    from gotit.db.ops.interview import interview_focus_for_today

    target = day or date.today()
    plan = await get_plan(session, target, user_id=user_id)
    notes = await list_notes(session, target, user_id=user_id, full_body=False)
    due_rows = await list_due_claims(session, target, user_id=user_id)
    due_claims = await _due_claim_views(
        session, due_rows, as_of=target, user_id=user_id
    )
    day_row = await ensure_day(session, target, user_id=user_id)
    summary = _close_summary_from_row(day_row)
    as_of = now if now is not None else datetime.now(UTC)
    interview_focus = await interview_focus_for_today(
        session, as_of, user_id=user_id
    )
    from gotit.db.ops.bootcamp import resolve_bootcamp

    bootcamp = await resolve_bootcamp(session, user_id=user_id)
    return TodayView(
        date=target,
        plan=plan,
        notes=notes,
        due_claims=due_claims,
        day_closed=day_row.closed_at is not None,
        close_suggested=_suggest_close(due_claims, plan.items),
        close_summary=summary,
        interview_focus=interview_focus,
        bootcamp=bootcamp,
    )


def _plan_item_status_value(item: PlanItemView | PlanItemRow) -> str:
    status = item.status
    return status.value if hasattr(status, "value") else str(status)


def _suggest_close(due_claims: list[Claim], plan_items: list[PlanItemView]) -> bool:
    """Heuristic only — owed clear and claim-linked plan items verified."""
    if due_claims:
        return False
    verify_items = [i for i in plan_items if i.claim_id is not None]
    if not verify_items:
        return True
    done = {PlanItemStatus.VERIFIED.value, PlanItemStatus.DEFERRED.value}
    return all(_plan_item_status_value(i) in done for i in verify_items)


def _close_summary_from_row(row: LearningDayRow) -> DayCloseSummary | None:
    if row.closed_at is None:
        return None
    closed = row.closed_at
    if closed.tzinfo is None:
        closed = closed.replace(tzinfo=UTC)
    return DayCloseSummary(
        passed_count=int(row.close_passed_count or 0),
        still_owed_count=int(row.close_still_owed_count or 0),
        note=(row.close_note or "").strip(),
        closed_at=closed,
    )


def _default_close_note(*, passed: int, still_owed: int) -> str:
    if still_owed <= 0:
        return f"过了 {passed} 道，欠清了" if passed else "今天收工了"
    return f"过了 {passed} 道，还挂 {still_owed} 道"


async def close_today(
    session: AsyncSession,
    day: date | None = None,
    *,
    user_id: str = DEFAULT_USER_ID,
    note: str | None = None,
) -> DayCloseSummary:
    """Mark the learning day closed. Idempotent — second call returns existing."""
    target = day or date.today()
    day_row = await ensure_day(session, target, user_id=user_id)
    existing = _close_summary_from_row(day_row)
    if existing is not None:
        return existing

    plan = await get_plan(session, target, user_id=user_id)
    due_rows = await list_due_claims(session, target, user_id=user_id)
    passed = sum(
        1 for i in plan.items if _plan_item_status_value(i) == PlanItemStatus.VERIFIED.value
    )
    still_owed = len(due_rows)
    clipped = (note or "").strip()[:200]
    auto = _default_close_note(passed=passed, still_owed=still_owed)
    day_row.closed_at = datetime.now(UTC)
    day_row.close_passed_count = passed
    day_row.close_still_owed_count = still_owed
    day_row.close_note = clipped or auto
    await session.flush()
    summary = _close_summary_from_row(day_row)
    assert summary is not None
    return summary
