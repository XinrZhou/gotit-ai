"""Project library CRUD and progress."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gotit.core.models import MasteryStatus, Project, ProjectProgress, ProjectStatus
from gotit.db.models import ClaimRow, ProjectRow
from gotit.db.ops._common import DEFAULT_USER_ID


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
