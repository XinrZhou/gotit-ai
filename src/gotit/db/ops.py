"""Shared day/plan/note/claim operations used by REST and MCP."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Select, delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from gotit.core.models import (
    ChatMessageView,
    Claim,
    DayNoteView,
    DayPlanView,
    DrillMaterial,
    DrillRound,
    DrillSession,
    HarnessCaseResult,
    HarnessRun,
    MasteryStatus,
    MemoryEntry,
    PlanItemSource,
    PlanItemStatus,
    PlanItemView,
    Project,
    ProjectProgress,
    ProjectStatus,
    PromptVersion,
    ResumeDocument,
    ResumeRecord,
    TodayView,
)
from gotit.db.models import (
    ChatMessageRow,
    ClaimRow,
    DayNoteRow,
    DrillMaterialRow,
    DrillSessionRow,
    HarnessCaseResultRow,
    HarnessRunRow,
    LearningDayRow,
    MemoryEntryRow,
    PlanItemRow,
    ProjectRow,
    PromptVersionRow,
    ResumeRow,
)

DEFAULT_USER_ID = "local"
EXCERPT_LEN = 240


def _excerpt(body: str, limit: int = EXCERPT_LEN) -> str:
    text = body.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _plan_item_view(row: PlanItemRow, *, topic: str | None = None) -> PlanItemView:
    return PlanItemView(
        id=row.id,
        title=row.title,
        source=PlanItemSource(row.source),
        status=PlanItemStatus(row.status),
        claim_id=row.claim_id,
        sort_order=row.sort_order,
        due_at=row.due_at,
        project_id=row.project_id,
        topic=topic,
    )


def _note_view(row: DayNoteRow, *, full_body: bool = False) -> DayNoteView:
    claim_ids = [UUID(str(c)) for c in (row.claim_ids or [])]
    body = row.body if full_body else ""
    day = row.learning_day.day if row.learning_day is not None else None
    return DayNoteView(
        id=row.id,
        title=row.title,
        body=body if full_body else _excerpt(row.body),
        excerpt=_excerpt(row.body),
        tags=list(row.tags or []),
        claim_ids=claim_ids,
        created_at=row.created_at or datetime.now(UTC),
        project_id=row.project_id,
        day=day,
    )


def _claim_view(row: ClaimRow) -> Claim:
    return Claim(
        id=row.id,
        text=row.text,
        source_excerpt=row.source_excerpt,
        status=MasteryStatus(row.status),
        source_note_id=row.source_note_id,
        next_review_at=row.next_review_at,
        topic=row.topic,
        tags=list(row.tags or []),
        project_id=row.project_id,
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
    # batch-fetch topic from associated claims
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


async def ingest_note(
    session: AsyncSession,
    note_id: UUID,
    *,
    claims: list[Claim] | None = None,
    user_id: str = DEFAULT_USER_ID,
    add_plan_item: bool = True,
) -> dict[str, object]:
    """Persist claims for a note. `claims` defaults to a stub extraction."""
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
    learning_day = await ensure_day(session, day, user_id=user_id)
    existing_claim_ids = {i.claim_id for i in learning_day.plan_items if i.claim_id is not None}
    next_order = max((i.sort_order for i in learning_day.plan_items), default=-1) + 1
    added = 0
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
        added += 1
    await session.flush()
    session.expire_all()
    return await get_plan(session, day, user_id=user_id)


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


async def apply_examine_verdict(
    session: AsyncSession,
    claim_id: UUID,
    *,
    verdict: str,
    user_id: str = DEFAULT_USER_ID,
    as_of: date | None = None,
) -> dict[str, object]:
    """Writeback for continuous verdicts: passed | almost | owe_next.

    - passed     → claim MASTERED, plan items VERIFIED
    - almost     → claim IN_PROGRESS, plan items IN_PROGRESS (stays today)
    - owe_next   → claim QUEUED, plan items FAILED, next_review_at +1d
    """
    today = as_of or date.today()
    claim = await session.get(ClaimRow, claim_id)
    if claim is None or claim.user_id != user_id:
        raise KeyError(f"claim not found: {claim_id}")

    stmt = select(PlanItemRow).where(PlanItemRow.claim_id == claim_id)
    items = list((await session.execute(stmt)).scalars().all())

    if verdict == "passed":
        claim.status = MasteryStatus.MASTERED.value
        claim.next_review_at = None
        for item in items:
            item.status = PlanItemStatus.VERIFIED.value
    elif verdict == "almost":
        claim.status = MasteryStatus.IN_PROGRESS.value
        for item in items:
            item.status = PlanItemStatus.IN_PROGRESS.value
    elif verdict == "owe_next":
        claim.status = MasteryStatus.QUEUED.value
        claim.next_review_at = today + timedelta(days=1)
        for item in items:
            item.status = PlanItemStatus.FAILED.value
    else:
        raise ValueError(f"unknown verdict: {verdict}")

    await session.flush()
    return {
        "claim": _claim_view(claim).model_dump(mode="json"),
        "plan_items": [_plan_item_view(i).model_dump(mode="json") for i in items],
        "verdict": verdict,
    }


# --- Prompt management ---


def _prompt_view(row: PromptVersionRow) -> PromptVersion:
    return PromptVersion(
        id=row.id,
        agent_name=row.agent_name,
        version_label=row.version_label,
        content_hash=row.content_hash,
        system_prompt=row.system_prompt,
        config=dict(row.config or {}),
        notes=row.notes,
        created_at=row.created_at or datetime.now(UTC),
        is_active=bool(row.is_active),
    )


async def register_prompts(
    session: AsyncSession,
    versions: list[PromptVersion],
) -> list[PromptVersion]:
    """Upsert prompt versions; the latest per agent becomes the active one."""
    if not versions:
        return []
    agents = {v.agent_name for v in versions}
    for v in versions:
        existing = await session.get(PromptVersionRow, v.id)
        if existing is None:
            session.add(
                PromptVersionRow(
                    id=v.id,
                    agent_name=v.agent_name,
                    version_label=v.version_label,
                    content_hash=v.content_hash,
                    system_prompt=v.system_prompt,
                    config=dict(v.config),
                    notes=v.notes,
                    created_at=v.created_at,
                    is_active=False,
                )
            )
        else:
            existing.content_hash = v.content_hash
            existing.system_prompt = v.system_prompt
            existing.config = dict(v.config)
            existing.notes = v.notes
    await session.flush()

    # Mark the newest version per agent as active; deactivate the rest.
    stmt = select(PromptVersionRow).where(PromptVersionRow.agent_name.in_(agents))
    rows = list((await session.execute(stmt)).scalars().all())
    by_agent: dict[str, list[PromptVersionRow]] = {}
    for r in rows:
        by_agent.setdefault(r.agent_name, []).append(r)
    for agent_rows in by_agent.values():
        agent_rows.sort(
            key=lambda r: r.created_at or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
        for i, r in enumerate(agent_rows):
            r.is_active = i == 0
    await session.flush()
    return [_prompt_view(r) for r in rows]


async def get_active_prompt(
    session: AsyncSession,
    agent_name: str,
) -> PromptVersion | None:
    stmt = select(PromptVersionRow).where(
        PromptVersionRow.agent_name == agent_name,
        PromptVersionRow.is_active.is_(True),
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    return _prompt_view(row) if row is not None else None


async def list_prompts(
    session: AsyncSession,
    *,
    agent_name: str | None = None,
    active_only: bool = False,
) -> list[PromptVersion]:
    stmt = select(PromptVersionRow)
    if agent_name is not None:
        stmt = stmt.where(PromptVersionRow.agent_name == agent_name)
    if active_only:
        stmt = stmt.where(PromptVersionRow.is_active.is_(True))
    stmt = stmt.order_by(PromptVersionRow.agent_name, PromptVersionRow.created_at)
    rows = list((await session.execute(stmt)).scalars().all())
    return [_prompt_view(r) for r in rows]


# --- Memory system ---


def _memory_view(row: MemoryEntryRow) -> MemoryEntry:
    return MemoryEntry(
        id=row.id,
        user_id=row.user_id,
        layer=row.layer,
        kind=row.kind,
        topic=row.topic,
        content=dict(row.content or {}),
        source=dict(row.source or {}),
        created_at=row.created_at or datetime.now(UTC),
        expires_at=row.expires_at,
    )


async def add_memory(
    session: AsyncSession,
    *,
    user_id: str,
    layer: str,
    kind: str,
    content: dict[str, Any],
    topic: str | None = None,
    source: dict[str, Any] | None = None,
    expires_at: datetime | None = None,
) -> MemoryEntry:
    row = MemoryEntryRow(
        id=uuid4(),
        user_id=user_id,
        layer=layer,
        kind=kind,
        topic=topic,
        content=dict(content),
        source=dict(source or {}),
        created_at=datetime.now(UTC),
        expires_at=expires_at,
    )
    session.add(row)
    await session.flush()
    return _memory_view(row)


async def list_memory(
    session: AsyncSession,
    *,
    user_id: str,
    layer: str | None = None,
    kind: str | None = None,
    topic: str | None = None,
    limit: int = 50,
) -> list[MemoryEntry]:
    stmt = select(MemoryEntryRow).where(MemoryEntryRow.user_id == user_id)
    if layer is not None:
        stmt = stmt.where(MemoryEntryRow.layer == layer)
    if kind is not None:
        stmt = stmt.where(MemoryEntryRow.kind == kind)
    if topic is not None:
        stmt = stmt.where(MemoryEntryRow.topic == topic)
    stmt = stmt.order_by(MemoryEntryRow.created_at.desc()).limit(limit)
    rows = list((await session.execute(stmt)).scalars().all())
    return [_memory_view(r) for r in rows]


# --- Harness persistence ---


def _harness_run_view(row: HarnessRunRow) -> HarnessRun:
    return HarnessRun(
        id=row.id,
        started_at=row.started_at or datetime.now(UTC),
        git_sha=row.git_sha,
        prompt_versions=dict(row.prompt_versions or {}),
        label=row.label,
        case_set=row.case_set,
        summary=dict(row.summary or {}),
        verdict=row.verdict,
        created_at=row.created_at or datetime.now(UTC),
    )


def _harness_case_view(row: HarnessCaseResultRow) -> HarnessCaseResult:
    return HarnessCaseResult(
        id=row.id,
        run_id=row.run_id,
        case_id=row.case_id,
        case_type=row.case_type,
        layer=row.layer,
        passed=bool(row.passed),
        score=row.score,
        metrics=dict(row.metrics or {}),
        trace=list(row.trace or []),
        created_at=row.created_at or datetime.now(UTC),
    )


async def add_harness_run(
    session: AsyncSession,
    *,
    started_at: datetime,
    case_set: str,
    label: str | None = None,
    git_sha: str | None = None,
    prompt_versions: dict[str, str] | None = None,
) -> HarnessRun:
    row = HarnessRunRow(
        id=uuid4(),
        started_at=started_at,
        git_sha=git_sha,
        prompt_versions=dict(prompt_versions or {}),
        label=label,
        case_set=case_set,
        summary={},
        verdict=None,
        created_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()
    return _harness_run_view(row)


async def add_harness_case_result(
    session: AsyncSession,
    *,
    run_id: UUID,
    case_id: str,
    case_type: str,
    layer: str,
    passed: bool,
    score: float | None = None,
    metrics: dict[str, Any] | None = None,
    trace: list[Any] | None = None,
) -> HarnessCaseResult:
    row = HarnessCaseResultRow(
        id=uuid4(),
        run_id=run_id,
        case_id=case_id,
        case_type=case_type,
        layer=layer,
        passed=passed,
        score=score,
        metrics=dict(metrics or {}),
        trace=list(trace or []),
        created_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()
    return _harness_case_view(row)


async def finalize_harness_run(
    session: AsyncSession,
    run_id: UUID,
    *,
    summary: dict[str, Any],
    verdict: str,
) -> None:
    row = await session.get(HarnessRunRow, run_id)
    if row is None:
        raise KeyError(f"harness run not found: {run_id}")
    row.summary = dict(summary)
    row.verdict = verdict
    await session.flush()


async def list_harness_runs(
    session: AsyncSession,
    *,
    label: str | None = None,
    limit: int = 50,
) -> list[HarnessRun]:
    stmt = select(HarnessRunRow).order_by(HarnessRunRow.created_at.desc()).limit(limit)
    if label is not None:
        stmt = stmt.where(HarnessRunRow.label == label)
    rows = list((await session.execute(stmt)).scalars().all())
    return [_harness_run_view(r) for r in rows]


async def list_harness_case_results(
    session: AsyncSession,
    *,
    run_id: UUID | None = None,
    case_id: str | None = None,
    limit: int = 200,
) -> list[HarnessCaseResult]:
    stmt = select(HarnessCaseResultRow).order_by(
        HarnessCaseResultRow.created_at.desc()
    ).limit(limit)
    if run_id is not None:
        stmt = stmt.where(HarnessCaseResultRow.run_id == run_id)
    if case_id is not None:
        stmt = stmt.where(HarnessCaseResultRow.case_id == case_id)
    rows = list((await session.execute(stmt)).scalars().all())
    return [_harness_case_view(r) for r in rows]


# --- Project drill ---


def _project_view(row: ProjectRow) -> Project:
    return Project(
        id=row.id,
        user_id=row.user_id,
        name=row.name,
        role=row.role,
        goal=row.goal,
        tech_stack=list(row.tech_stack or []),
        status=ProjectStatus(row.status),
        created_at=row.created_at or datetime.now(UTC),
    )


async def create_project(
    session: AsyncSession,
    *,
    name: str,
    role: str | None = None,
    goal: str | None = None,
    tech_stack: list[str] | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> Project:
    row = ProjectRow(
        id=uuid4(),
        user_id=user_id,
        name=name.strip(),
        role=role,
        goal=goal,
        tech_stack=list(tech_stack or []),
        status=ProjectStatus.ACTIVE.value,
        created_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()
    return _project_view(row)


async def list_projects(
    session: AsyncSession,
    *,
    user_id: str = DEFAULT_USER_ID,
    include_archived: bool = False,
) -> list[Project]:
    stmt = select(ProjectRow).where(ProjectRow.user_id == user_id)
    if not include_archived:
        stmt = stmt.where(ProjectRow.status == ProjectStatus.ACTIVE.value)
    stmt = stmt.order_by(ProjectRow.created_at.desc())
    rows = list((await session.execute(stmt)).scalars().all())
    return [_project_view(r) for r in rows]


async def get_project(
    session: AsyncSession,
    project_id: UUID,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> Project:
    row = await session.get(ProjectRow, project_id)
    if row is None or row.user_id != user_id:
        raise KeyError(f"project not found: {project_id}")
    return _project_view(row)


async def update_project(
    session: AsyncSession,
    project_id: UUID,
    *,
    user_id: str = DEFAULT_USER_ID,
    name: str | None = None,
    role: str | None = None,
    goal: str | None = None,
    tech_stack: list[str] | None = None,
    status: ProjectStatus | None = None,
) -> Project:
    row = await session.get(ProjectRow, project_id)
    if row is None or row.user_id != user_id:
        raise KeyError(f"project not found: {project_id}")
    if name is not None:
        row.name = name.strip()
    if role is not None:
        row.role = role
    if goal is not None:
        row.goal = goal
    if tech_stack is not None:
        row.tech_stack = list(tech_stack)
    if status is not None:
        row.status = status.value
    await session.flush()
    return _project_view(row)


async def archive_project(
    session: AsyncSession,
    project_id: UUID,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> Project:
    return await update_project(
        session, project_id, user_id=user_id, status=ProjectStatus.ARCHIVED
    )


async def list_project_claims(
    session: AsyncSession,
    project_id: UUID,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> list[Claim]:
    stmt = select(ClaimRow).where(
        ClaimRow.project_id == project_id, ClaimRow.user_id == user_id
    )
    rows = list((await session.execute(stmt)).scalars().all())
    return [_claim_view(r) for r in rows]


async def list_topic_claims_today(
    session: AsyncSession,
    topic: str,
    *,
    user_id: str = DEFAULT_USER_ID,
    as_of: date | None = None,
) -> list[Claim]:
    """Today's plan-item claims matching `topic` and not yet mastered."""
    target = as_of or date.today()
    learning_day = await ensure_day(session, target, user_id=user_id)
    item_claim_ids = [i.claim_id for i in learning_day.plan_items if i.claim_id]
    if not item_claim_ids:
        return []
    order = {i.claim_id: i.sort_order for i in learning_day.plan_items if i.claim_id}
    stmt = select(ClaimRow).where(
        ClaimRow.user_id == user_id,
        ClaimRow.id.in_(item_claim_ids),
        ClaimRow.topic == topic,
        ClaimRow.status != MasteryStatus.MASTERED.value,
    )
    rows = list((await session.execute(stmt)).scalars().all())
    rows.sort(key=lambda r: (order.get(r.id, 0), str(r.id)))
    return [_claim_view(r) for r in rows]


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


async def project_progress(
    session: AsyncSession,
    project_id: UUID,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> ProjectProgress:
    stmt = select(ClaimRow).where(
        ClaimRow.project_id == project_id, ClaimRow.user_id == user_id
    )
    rows = list((await session.execute(stmt)).scalars().all())
    mastered = sum(1 for r in rows if r.status == MasteryStatus.MASTERED.value)
    in_progress = sum(1 for r in rows if r.status == MasteryStatus.IN_PROGRESS.value)
    not_yet = sum(
        1
        for r in rows
        if r.status not in (MasteryStatus.MASTERED.value, MasteryStatus.IN_PROGRESS.value)
    )
    return ProjectProgress(
        claims_total=len(rows),
        mastered=mastered,
        in_progress=in_progress,
        not_yet=not_yet,
    )


# --- Resume-driven drill: resume / materials / sessions ---


def _resume_view(row: ResumeRow) -> ResumeRecord:
    return ResumeRecord(
        id=row.id,
        user_id=row.user_id,
        upload_id=row.upload_id,
        file_path=row.file_path,
        document=ResumeDocument.model_validate(row.document),
        created_at=row.created_at,
    )


def _drill_material_view(row: DrillMaterialRow) -> DrillMaterial:
    return DrillMaterial(
        id=row.id,
        user_id=row.user_id,
        title=row.title,
        body=row.body,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _drill_session_view(row: DrillSessionRow) -> DrillSession:
    return DrillSession(
        id=row.id,
        user_id=row.user_id,
        resume_id=row.resume_id,
        round=DrillRound(row.round),
        direction=row.direction,
        project_id=row.project_id,
        status=row.status,
        started_at=row.started_at,
        ended_at=row.ended_at,
        messages=list(row.messages or []),
    )


async def upsert_resume(
    session: AsyncSession,
    *,
    upload_id: UUID,
    file_path: str,
    document: ResumeDocument,
    user_id: str = DEFAULT_USER_ID,
) -> ResumeRecord:
    """Insert or replace the global resume record for a user."""
    existing = await session.get(ResumeRow, _resume_pk(user_id))
    if existing is None:
        existing = await session.scalar(
            select(ResumeRow).where(ResumeRow.user_id == user_id)
        )
    now = datetime.now(UTC)
    if existing is None:
        row = ResumeRow(
            id=_resume_pk(user_id),
            user_id=user_id,
            upload_id=upload_id,
            file_path=file_path,
            document=document.model_dump(mode="json"),
            created_at=now,
        )
        session.add(row)
        await session.flush()
        return _resume_view(row)
    existing.upload_id = upload_id
    existing.file_path = file_path
    existing.document = document.model_dump(mode="json")
    existing.created_at = now
    await session.flush()
    return _resume_view(existing)


def _resume_pk(user_id: str) -> UUID:
    """Stable PK per user so upsert replaces the single global resume."""
    from uuid import NAMESPACE_DNS, uuid5

    return uuid5(NAMESPACE_DNS, f"gotit-resume:{user_id}")


async def get_resume(
    session: AsyncSession,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> ResumeRecord | None:
    row = await session.scalar(select(ResumeRow).where(ResumeRow.user_id == user_id))
    return _resume_view(row) if row else None


async def apply_resume(
    session: AsyncSession,
    document: ResumeDocument,
    *,
    upload_id: UUID,
    file_path: str,
    ingest: bool = False,
    user_id: str = DEFAULT_USER_ID,
) -> dict[str, object]:
    """Clear-rebuild the project library from a parsed resume.

    - Delete all existing projects (and resume-derived notes with tag "resume")
    - Detach user hand-written notes/claims/plan_items (project_id -> NULL)
    - Create fresh projects + one resume-note per project (tags=["resume"])
    - Upsert the global resume record
    Returns {projects, notes, claims}.
    """
    # 1. Collect old projects
    old_projects = list(
        (await session.execute(select(ProjectRow).where(ProjectRow.user_id == user_id)))
        .scalars()
        .all()
    )
    old_project_ids = [p.id for p in old_projects]

    # 2. Delete resume-derived notes (tags contains "resume") — derived data, safe.
    all_notes = list(
        (
            await session.execute(
                select(DayNoteRow).join(
                    LearningDayRow, DayNoteRow.day_id == LearningDayRow.id
                ).where(LearningDayRow.user_id == user_id)
            )
        ).scalars().all()
    )
    resume_notes = [n for n in all_notes if "resume" in (n.tags or [])]
    for n in resume_notes:
        await session.delete(n)

    # 3. Detach user hand-written notes/claims/plan_items from old projects.
    if old_project_ids:
        await session.execute(
            update(DayNoteRow).where(DayNoteRow.project_id.in_(old_project_ids)).values(
                project_id=None
            )
        )
        await session.execute(
            update(ClaimRow).where(ClaimRow.project_id.in_(old_project_ids)).values(
                project_id=None
            )
        )
        await session.execute(
            update(PlanItemRow).where(PlanItemRow.project_id.in_(old_project_ids)).values(
                project_id=None
            )
        )

    # 4. Delete old projects.
    if old_project_ids:
        await session.execute(
            delete(ProjectRow).where(ProjectRow.id.in_(old_project_ids))
        )

    # 5. Rebuild.
    today = date.today()
    created_projects: list[Project] = []
    created_notes: list[DayNoteView] = []
    created_claims: list[list[Claim]] = []
    for pp in document.projects:
        project = await create_project(
            session,
            name=pp.name,
            role=pp.role,
            goal=pp.goal,
            tech_stack=pp.tech_stack,
            user_id=user_id,
        )
        created_projects.append(project)
        note = await add_note(
            session,
            today,
            pp.description,
            title=pp.name,
            tags=["resume"],
            user_id=user_id,
            project_id=project.id,
        )
        created_notes.append(note)
        claims: list[Claim] = []
        if ingest:
            result = await ingest_note(session, note.id, user_id=user_id)
            raw_claims = result["claims"]
            assert isinstance(raw_claims, list)
            claims = [Claim.model_validate(c) for c in raw_claims]
        created_claims.append(claims)

    # 6. Upsert global resume record.
    await upsert_resume(
        session, upload_id=upload_id, file_path=file_path, document=document, user_id=user_id
    )

    return {
        "projects": [p.model_dump(mode="json") for p in created_projects],
        "notes": [n.model_dump(mode="json") for n in created_notes],
        "claims": [c.model_dump(mode="json") for cl in created_claims for c in cl],
    }


async def list_drill_materials(
    session: AsyncSession,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> list[DrillMaterial]:
    stmt = (
        select(DrillMaterialRow)
        .where(DrillMaterialRow.user_id == user_id)
        .order_by(DrillMaterialRow.created_at.desc())
    )
    rows = list((await session.execute(stmt)).scalars().all())
    return [_drill_material_view(r) for r in rows]


async def upsert_drill_material(
    session: AsyncSession,
    *,
    material_id: UUID | None = None,
    title: str,
    body: str,
    user_id: str = DEFAULT_USER_ID,
) -> DrillMaterial:
    now = datetime.now(UTC)
    if material_id is not None:
        row = await session.get(DrillMaterialRow, material_id)
        if row is not None and row.user_id == user_id:
            row.title = title.strip()
            row.body = body.strip()
            row.updated_at = now
            await session.flush()
            return _drill_material_view(row)
    row = DrillMaterialRow(
        id=uuid4(),
        user_id=user_id,
        title=title.strip(),
        body=body.strip(),
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    await session.flush()
    return _drill_material_view(row)


async def delete_drill_material(
    session: AsyncSession,
    material_id: UUID,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> None:
    row = await session.get(DrillMaterialRow, material_id)
    if row is None or row.user_id != user_id:
        raise KeyError(f"drill material not found: {material_id}")
    await session.delete(row)
    await session.flush()


async def create_drill_session(
    session: AsyncSession,
    *,
    resume_id: UUID,
    round_: DrillRound,
    direction: str | None = None,
    project_id: UUID | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> DrillSession:
    row = DrillSessionRow(
        id=uuid4(),
        user_id=user_id,
        resume_id=resume_id,
        round=round_.value,
        direction=direction,
        project_id=project_id,
        status="active",
        started_at=datetime.now(UTC),
        ended_at=None,
        messages=[],
    )
    session.add(row)
    await session.flush()
    return _drill_session_view(row)


async def append_drill_message(
    session: AsyncSession,
    session_id: UUID,
    *,
    role: str,
    text: str,
    user_id: str = DEFAULT_USER_ID,
) -> DrillSession:
    row = await session.get(DrillSessionRow, session_id)
    if row is None or row.user_id != user_id:
        raise KeyError(f"drill session not found: {session_id}")
    msgs = list(row.messages or [])
    msgs.append({"role": role, "text": text})
    row.messages = msgs
    await session.flush()
    return _drill_session_view(row)


async def finish_drill_session(
    session: AsyncSession,
    session_id: UUID,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> DrillSession:
    row = await session.get(DrillSessionRow, session_id)
    if row is None or row.user_id != user_id:
        raise KeyError(f"drill session not found: {session_id}")
    row.status = "done"
    row.ended_at = datetime.now(UTC)
    await session.flush()
    return _drill_session_view(row)


async def list_drill_sessions(
    session: AsyncSession,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> list[DrillSession]:
    stmt = (
        select(DrillSessionRow)
        .where(DrillSessionRow.user_id == user_id)
        .order_by(DrillSessionRow.started_at.desc())
    )
    rows = list((await session.execute(stmt)).scalars().all())
    return [_drill_session_view(r) for r in rows]


async def get_drill_session(
    session: AsyncSession,
    session_id: UUID,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> DrillSession:
    row = await session.get(DrillSessionRow, session_id)
    if row is None or row.user_id != user_id:
        raise KeyError(f"drill session not found: {session_id}")
    return _drill_session_view(row)
