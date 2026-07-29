"""Drill materials and resume-driven mock-interview sessions."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gotit.core.models import DrillMaterial, DrillRound, DrillSession
from gotit.db.models import DrillMaterialRow, DrillSessionRow
from gotit.db.ops._common import DEFAULT_USER_ID


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
