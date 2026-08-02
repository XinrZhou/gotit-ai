from __future__ import annotations

from uuid import UUID

from gotit.core.models import (
    ProjectStatus,
)
from gotit.db import ops as day_ops
from gotit.db import session_scope
from gotit.db.runtime import ensure_db
from gotit.mcp.app import mcp
from gotit.mcp.common import (
    _user_id,
)


@mcp.tool()
async def gotit_list_projects(include_archived: bool = False) -> list[dict[str, object]]:
    """List the learner's projects (active by default)."""
    await ensure_db()
    async with session_scope() as session:
        projects = await day_ops.list_projects(
            session, user_id=_user_id(), include_archived=include_archived
        )
    return [p.model_dump(mode="json") for p in projects]

@mcp.tool()
async def gotit_get_project(project_id: str) -> dict[str, object]:
    """Get a single project by id."""
    await ensure_db()
    async with session_scope() as session:
        project = await day_ops.get_project(
            session, UUID(project_id), user_id=_user_id()
        )
    return project.model_dump(mode="json")

@mcp.tool()
async def gotit_update_project(
    project_id: str,
    name: str | None = None,
    role: str | None = None,
    goal: str | None = None,
    tech_stack: list[str] | None = None,
    status: str | None = None,
) -> dict[str, object]:
    """Update a project's fields. Set status='archived' to archive."""
    await ensure_db()
    async with session_scope() as session:
        project = await day_ops.update_project(
            session,
            UUID(project_id),
            user_id=_user_id(),
            name=name,
            role=role,
            goal=goal,
            tech_stack=tech_stack,
            status=ProjectStatus(status) if status else None,
        )
    return project.model_dump(mode="json")

@mcp.tool()
async def gotit_delete_project(project_id: str) -> dict[str, object]:
    """Archive a project (soft-delete); it leaves the default library list."""
    await ensure_db()
    async with session_scope() as session:
        project = await day_ops.archive_project(
            session, UUID(project_id), user_id=_user_id()
        )
    return project.model_dump(mode="json")

@mcp.tool()
async def gotit_project_progress(project_id: str) -> dict[str, object]:
    """Return claim mastery progress for a project."""
    await ensure_db()
    async with session_scope() as session:
        progress = await day_ops.project_progress(
            session, UUID(project_id), user_id=_user_id()
        )
    return progress.model_dump(mode="json")

