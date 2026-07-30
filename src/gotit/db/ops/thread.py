"""Thread / message / ball-custody operations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gotit.core.models import BallCustody, BallStage, Message, Thread
from gotit.db.models import BallCustodyRow, MessageRow, ThreadRow
from gotit.db.ops._common import _as_utc


def _thread_view(row: ThreadRow) -> Thread:
    return Thread(
        id=row.id,
        user_id=row.user_id,
        title=row.title,
        kind=row.kind,  # type: ignore[arg-type]
        status=row.status,
        created_at=_as_utc(row.created_at),
        updated_at=_as_utc(row.updated_at),
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
        created_at=_as_utc(row.created_at),
    )


def _ball_view(row: BallCustodyRow) -> BallCustody:
    return BallCustody(
        id=row.id,
        thread_id=row.thread_id,
        holder=row.holder,
        stage=row.stage,  # type: ignore[arg-type]
        context=dict(row.context or {}),
        acquired_at=_as_utc(row.acquired_at),
        expires_at=_as_utc(row.expires_at) if row.expires_at is not None else None,
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


async def update_thread_title(
    session: AsyncSession,
    thread_id: UUID,
    *,
    title: str,
) -> Thread | None:
    row = await session.get(ThreadRow, thread_id)
    if row is None:
        return None
    row.title = title
    row.updated_at = datetime.now(UTC)
    await session.flush()
    return _thread_view(row)


async def touch_thread(session: AsyncSession, thread_id: UUID) -> None:
    row = await session.get(ThreadRow, thread_id)
    if row is not None:
        row.updated_at = datetime.now(UTC)
        await session.flush()


async def delete_thread(
    session: AsyncSession,
    thread_id: UUID,
    *,
    user_id: str,
) -> bool:
    """Delete a thread and its messages / ball. Returns False if missing/forbidden."""
    row = await session.get(ThreadRow, thread_id)
    if row is None or row.user_id != user_id:
        return False
    msgs = list(
        (
            await session.execute(
                select(MessageRow).where(MessageRow.thread_id == thread_id)
            )
        )
        .scalars()
        .all()
    )
    for m in msgs:
        await session.delete(m)
    ball = (
        await session.execute(
            select(BallCustodyRow).where(BallCustodyRow.thread_id == thread_id)
        )
    ).scalar_one_or_none()
    if ball is not None:
        await session.delete(ball)
    await session.delete(row)
    await session.flush()
    return True


def derive_thread_title(text: str, *, max_len: int = 28) -> str:
    """Heuristic title from the first user message (no LLM)."""
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        return "新对话"
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1] + "…"


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
    await touch_thread(session, thread_id)
    return _message_view(row)


async def count_user_messages(session: AsyncSession, thread_id: UUID) -> int:
    from sqlalchemy import func

    stmt = (
        select(func.count())
        .select_from(MessageRow)
        .where(MessageRow.thread_id == thread_id, MessageRow.role == "user")
    )
    return int((await session.execute(stmt)).scalar_one())


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


async def append_workflow_exchange(
    session: AsyncSession,
    *,
    thread_id: UUID,
    user_id: str,
    workflow: str,
    agent_name: str,
    agent_text: str,
    user_text: str | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> list[Message]:
    """Write a workflow user+agent exchange into a thread the user owns.

    Raises ``KeyError`` when the thread is missing or not owned by ``user_id``.
    Skips empty agent text (user answer still written when present).
    """
    thread = await get_thread(session, thread_id)
    if thread is None or thread.user_id != user_id:
        raise KeyError(f"thread not found: {thread_id}")

    base: dict[str, Any] = {"workflow": workflow, **dict(extra_metadata or {})}
    out: list[Message] = []
    if user_text is not None and user_text.strip():
        out.append(
            await add_message(
                session,
                thread_id=thread_id,
                role="user",
                text=user_text.strip(),
                metadata={**base, "step": "answer"},
            )
        )
    if agent_text.strip():
        out.append(
            await add_message(
                session,
                thread_id=thread_id,
                role="agent",
                text=agent_text.strip(),
                agent_name=agent_name,
                metadata={**base, "step": "agent"},
            )
        )
    return out


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
