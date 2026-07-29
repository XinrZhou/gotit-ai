"""Resume upload/parse persistence and clear-rebuild apply."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import NAMESPACE_DNS, UUID, uuid5

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from gotit.core.models import Project, ResumeDocument, ResumeRecord
from gotit.db.models import ClaimRow, DayNoteRow, LearningDayRow, PlanItemRow, ProjectRow, ResumeRow
from gotit.db.ops._common import DEFAULT_USER_ID
from gotit.db.ops.project import create_project


def _resume_view(row: ResumeRow) -> ResumeRecord:
    return ResumeRecord(
        id=row.id,
        user_id=row.user_id,
        upload_id=row.upload_id,
        file_path=row.file_path,
        document=ResumeDocument.model_validate(row.document),
        created_at=row.created_at,
    )


def _resume_pk(user_id: str) -> UUID:
    """Stable PK per user so upsert replaces the single global resume."""
    return uuid5(NAMESPACE_DNS, f"gotit-resume:{user_id}")


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
    ingest: bool = False,  # noqa: ARG001 — kept for API compat; notes no longer created
    user_id: str = DEFAULT_USER_ID,
) -> dict[str, object]:
    """Clear-rebuild the project library from a parsed resume.

    - Delete all existing projects
    - Delete legacy resume-derived notes (tags contain ``resume``) if any
    - Detach user hand-written notes/claims/plan_items (project_id -> NULL)
    - Create fresh projects from ``document.projects``
    - Upsert the global resume record (Sage reads this during 深挖)

    Does **not** create DayNotes — resume projects are drill context, not quiz
    material. ``ingest`` is ignored (API/MCP compat).

    Returns ``{projects, notes=[], claims=[]}``.
    """
    del ingest  # unused; quiz ingest is a separate notes flow
    old_projects = list(
        (await session.execute(select(ProjectRow).where(ProjectRow.user_id == user_id)))
        .scalars()
        .all()
    )
    old_project_ids = [p.id for p in old_projects]

    all_notes = list(
        (
            await session.execute(
                select(DayNoteRow)
                .join(LearningDayRow, DayNoteRow.day_id == LearningDayRow.id)
                .where(LearningDayRow.user_id == user_id)
            )
        )
        .scalars()
        .all()
    )
    for n in all_notes:
        if "resume" in (n.tags or []):
            await session.delete(n)

    if old_project_ids:
        await session.execute(
            update(DayNoteRow)
            .where(DayNoteRow.project_id.in_(old_project_ids))
            .values(project_id=None)
        )
        await session.execute(
            update(ClaimRow)
            .where(ClaimRow.project_id.in_(old_project_ids))
            .values(project_id=None)
        )
        await session.execute(
            update(PlanItemRow)
            .where(PlanItemRow.project_id.in_(old_project_ids))
            .values(project_id=None)
        )
        await session.execute(
            delete(ProjectRow).where(ProjectRow.id.in_(old_project_ids))
        )

    created_projects: list[Project] = []
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

    await upsert_resume(
        session,
        upload_id=upload_id,
        file_path=file_path,
        document=document,
        user_id=user_id,
    )

    return {
        "projects": [p.model_dump(mode="json") for p in created_projects],
        "notes": [],
        "claims": [],
    }
