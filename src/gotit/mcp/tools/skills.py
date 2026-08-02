from __future__ import annotations

from gotit.db import ops as day_ops
from gotit.db import session_scope
from gotit.db.runtime import ensure_db
from gotit.mcp.app import mcp
from gotit.mcp.common import (
    _user_id,
)


@mcp.tool()
async def gotit_list_skills() -> list[dict[str, object]]:
    """List skill catalog (builtin + user installs) with enabled flags."""
    await ensure_db()
    async with session_scope() as session:
        items = await day_ops.list_skill_catalog(session, user_id=_user_id())
        return [s.model_dump(mode="json") for s in items]

@mcp.tool()
async def gotit_get_skill(name: str) -> dict[str, object]:
    """Get skill markdown for view/edit (editable=false for builtins)."""
    await ensure_db()
    try:
        async with session_scope() as session:
            detail = await day_ops.get_skill_detail(
                session, user_id=_user_id(), name=name
            )
            return detail.model_dump(mode="json")
    except KeyError as exc:
        return {"error": str(exc)}

@mcp.tool()
async def gotit_install_skill(markdown: str, name: str | None = None) -> dict[str, object]:
    """Install a skill from SKILL.md / markdown content (for companion agents)."""
    await ensure_db()
    try:
        async with session_scope() as session:
            skill = await day_ops.install_skill(
                session,
                user_id=_user_id(),
                raw_markdown=markdown,
                fallback_name=name,
            )
            return skill.model_dump(mode="json")
    except ValueError as exc:
        return {"error": str(exc)}

@mcp.tool()
async def gotit_update_skill(name: str, markdown: str) -> dict[str, object]:
    """Update markdown of a user-installed skill (name in frontmatter must match)."""
    await ensure_db()
    try:
        async with session_scope() as session:
            skill = await day_ops.update_skill_markdown(
                session,
                user_id=_user_id(),
                name=name,
                raw_markdown=markdown,
            )
            return skill.model_dump(mode="json")
    except (KeyError, ValueError) as exc:
        return {"error": str(exc)}

@mcp.tool()
async def gotit_set_skill_enabled(name: str, enabled: bool) -> dict[str, object]:
    """Enable or disable a skill in the catalog."""
    await ensure_db()
    try:
        async with session_scope() as session:
            skill = await day_ops.set_skill_enabled(
                session, user_id=_user_id(), name=name, enabled=enabled
            )
            return skill.model_dump(mode="json")
    except KeyError as exc:
        return {"error": str(exc)}

@mcp.tool()
async def gotit_delete_skill(name: str) -> dict[str, object]:
    """Delete a user-installed skill (or clear a builtin override)."""
    await ensure_db()
    try:
        async with session_scope() as session:
            await day_ops.delete_user_skill(session, user_id=_user_id(), name=name)
            return {"ok": True}
    except KeyError as exc:
        return {"error": str(exc)}

