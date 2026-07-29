"""Thread / message / ball-custody operations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gotit.core.models import BallCustody, BallStage, Message, Thread
from gotit.db.models import BallCustodyRow, MessageRow, ThreadRow


def _thread_view(row: ThreadRow) -> Thread:
    return Thread(
        id=row.id,
        user_id=row.user_id,
        title=row.title,
        kind=row.kind,  # type: ignore[arg-type]
        status=row.status,
        created_at=row.created_at or datetime.now(UTC),
        updated_at=row.updated_at or datetime.now(UTC),
    )


def _message_view(row: MessageRow) -> Message:
    return Message(
        id=row.id,
        thread_id=row.thread_id,
        agent_name=row.agent_name,
        role=row.role,  # type: ignore[arg-type]
        text=row.text,
        mentions=list(row.mentions or []),
        metadata=dict(row.metadata_ or {}),
        created_at=row.created_at or datetime.now(UTC),
    )


def _ball_view(row: BallCustodyRow) -> BallCustody:
    return BallCustody(
        id=row.id,
        thread_id=row.thread_id,
        holder=row.holder,
        stage=row.stage,  # type: ignore[arg-type]
        context=dict(row.context or {}),
        acquired_at=row.acquired_at or datetime.now(UTC),
        expires_at=row.expires_at,
    )


# --- threads ---


async def create_thread(
    session: AsyncSession,
    *,
    user_id: str,
    title: str,
    kind: str = "chat",
) -> Thread:
    row = ThreadRow(
        id=uuid4(),
        user_id=user_id,
        title=title,
        kind=kind,
        status="active",
    )
    session.add(row)
    await session.flush()
    return _thread_view(row)


async def list_threads(
    session: AsyncSession,
    *,
    user_id: str,
    kind: str | None = None,
) -> list[Thread]:
    stmt = select(ThreadRow).where(ThreadRow.user_id == user_id)
    if kind is not None:
        stmt = stmt.where(ThreadRow.kind == kind)
    stmt = stmt.order_by(ThreadRow.updated_at.desc())
    rows = list((await session.execute(stmt)).scalars().all())
    return [_thread_view(r) for r in rows]


async def get_thread(session: AsyncSession, thread_id: UUID) -> Thread | None:
    row = await session.get(ThreadRow, thread_id)
    return _thread_view(row) if row is not None else None


# --- messages ---


async def add_message(
    session: AsyncSession,
    *,
    thread_id: UUID,
    role: str,
    text: str,
    agent_name: str | None = None,
    mentions: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Message:
    row = MessageRow(
        id=uuid4(),
        thread_id=thread_id,
        agent_name=agent_name,
        role=role,
        text=text,
        mentions=list(mentions or []),
        metadata_=dict(metadata or {}),
    )
    session.add(row)
    await session.flush()
    return _message_view(row)


async def list_messages(
    session: AsyncSession,
    *,
    thread_id: UUID,
    limit: int = 200,
) -> list[Message]:
    stmt = (
        select(MessageRow)
        .where(MessageRow.thread_id == thread_id)
        .order_by(MessageRow.created_at.asc())
        .limit(limit)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    return [_message_view(r) for r in rows]


# --- ball custody ---


async def get_ball(session: AsyncSession, thread_id: UUID) -> BallCustody | None:
    stmt = select(BallCustodyRow).where(BallCustodyRow.thread_id == thread_id)
    row = (await session.execute(stmt)).scalar_one_or_none()
    return _ball_view(row) if row is not None else None


async def set_ball(
    session: AsyncSession,
    *,
    thread_id: UUID,
    holder: str,
    stage: BallStage | str,
    context: dict[str, Any] | None = None,
    expires_at: datetime | None = None,
) -> BallCustody:
    stmt = select(BallCustodyRow).where(BallCustodyRow.thread_id == thread_id)
    row = (await session.execute(stmt)).scalar_one_or_none()
    stage_val = stage.value if isinstance(stage, BallStage) else stage
    if row is None:
        row = BallCustodyRow(
            id=uuid4(),
            thread_id=thread_id,
            holder=holder,
            stage=stage_val,
            context=dict(context or {}),
            expires_at=expires_at,
        )
        session.add(row)
    else:
        row.holder = holder
        row.stage = stage_val
        row.context = dict(context or {})
        row.acquired_at = datetime.now(UTC)
        row.expires_at = expires_at
    await session.flush()
    return _ball_view(row)


async def clear_ball(session: AsyncSession, thread_id: UUID) -> None:
    stmt = select(BallCustodyRow).where(BallCustodyRow.thread_id == thread_id)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is not None:
        await session.delete(row)
        await session.flush()
