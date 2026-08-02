from __future__ import annotations

from pathlib import Path

from gotit.db import ops as day_ops
from gotit.db import session_scope
from gotit.db.runtime import ensure_db
from gotit.mcp.app import mcp


@mcp.tool()
async def gotit_list_prompts(
    agent_name: str | None = None,
    active_only: bool = False,
) -> list[dict[str, object]]:
    """List prompt versions (optionally filtered)."""
    await ensure_db()
    async with session_scope() as session:
        versions = await day_ops.list_prompts(
            session,
            agent_name=agent_name,
            active_only=active_only,
        )
    return [v.model_dump(mode="json") for v in versions]

@mcp.tool()
async def gotit_register_prompts() -> list[dict[str, object]]:
    """Load prompts/*.md into the database and mark the newest per agent active."""

    from gotit.prompts import load_prompt_dir

    await ensure_db()
    versions = load_prompt_dir(Path("prompts"))
    async with session_scope() as session:
        registered = await day_ops.register_prompts(session, versions)
    return [v.model_dump(mode="json") for v in registered]


# --- Project drill ---

