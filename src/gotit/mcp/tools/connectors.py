from __future__ import annotations

from uuid import UUID

from gotit.db import ops as day_ops
from gotit.db import session_scope
from gotit.db.runtime import ensure_db
from gotit.mcp.app import mcp
from gotit.mcp.common import (
    _user_id,
)


@mcp.tool()
async def gotit_list_connectors() -> list[dict[str, object]]:
    """List MCP connectors configured for companion agents."""
    await ensure_db()
    async with session_scope() as session:
        items = await day_ops.list_connectors(session, user_id=_user_id())
        return [c.model_dump(mode="json") for c in items]

@mcp.tool()
async def gotit_upsert_connector(
    name: str,
    transport: str,
    config: dict[str, object] | None = None,
    enabled: bool = True,
) -> dict[str, object]:
    """Create or replace an MCP connector (stdio | http | sse)."""
    await ensure_db()
    if transport not in ("stdio", "http", "sse"):
        return {"error": "transport must be stdio|http|sse"}
    try:
        async with session_scope() as session:
            conn = await day_ops.upsert_connector(
                session,
                user_id=_user_id(),
                name=name,
                transport=transport,  # type: ignore[arg-type]
                config=dict(config or {}),
                enabled=enabled,
            )
            return conn.model_dump(mode="json")
    except ValueError as exc:
        return {"error": str(exc)}

@mcp.tool()
async def gotit_import_connectors(
    config: dict[str, object],
) -> list[dict[str, object]] | dict[str, object]:
    """Import connectors from Claude/Cursor-style mcpServers JSON."""
    await ensure_db()
    try:
        async with session_scope() as session:
            items = await day_ops.import_connectors(
                session, user_id=_user_id(), payload=dict(config)
            )
            return [c.model_dump(mode="json") for c in items]
    except ValueError as exc:
        return {"error": str(exc)}

@mcp.tool()
async def gotit_delete_connector(connector_id: str) -> dict[str, object]:
    """Delete an MCP connector by id."""
    await ensure_db()
    try:
        async with session_scope() as session:
            await day_ops.delete_connector(
                session, user_id=_user_id(), connector_id=UUID(connector_id)
            )
            return {"ok": True}
    except (KeyError, ValueError) as exc:
        return {"error": str(exc)}

