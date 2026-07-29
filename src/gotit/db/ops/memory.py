"""Long/working/session memory entries."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gotit.core.models import MemoryEntry
from gotit.db.models import MemoryEntryRow


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
