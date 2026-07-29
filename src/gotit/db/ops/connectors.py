"""MCP connectors CRUD (Settings → 连接器)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gotit.core.models import McpConnector
from gotit.db.models import McpConnectorRow

Transport = Literal["stdio", "http", "sse"]


def _view(row: McpConnectorRow) -> McpConnector:
    return McpConnector(
        id=row.id,
        user_id=row.user_id,
        name=row.name,
        transport=row.transport,  # type: ignore[arg-type]
        config=dict(row.config or {}),
        enabled=bool(row.enabled),
        last_status=row.last_status,  # type: ignore[arg-type]
        last_error=row.last_error,
        created_at=row.created_at or datetime.now(UTC),
        updated_at=row.updated_at or datetime.now(UTC),
    )


def normalize_connector_config(
    transport: Transport,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Validate and normalize connector config for storage."""
    cfg = dict(config or {})
    if transport == "stdio":
        command = str(cfg.get("command") or "").strip()
        if not command:
            raise ValueError("stdio connector requires config.command")
        args = cfg.get("args") or []
        if not isinstance(args, list):
            raise ValueError("config.args must be a list")
        env = cfg.get("env") or {}
        if not isinstance(env, dict):
            raise ValueError("config.env must be an object")
        return {
            "command": command,
            "args": [str(a) for a in args],
            "env": {str(k): str(v) for k, v in env.items()},
        }
    url = str(cfg.get("url") or "").strip()
    if not url:
        raise ValueError(f"{transport} connector requires config.url")
    headers = cfg.get("headers") or {}
    if not isinstance(headers, dict):
        raise ValueError("config.headers must be an object")
    return {
        "url": url,
        "headers": {str(k): str(v) for k, v in headers.items()},
    }


def parse_mcp_servers_json(payload: dict[str, Any]) -> list[tuple[str, Transport, dict[str, Any]]]:
    """Parse Claude/Cursor-style `{mcpServers: {...}}` or bare server map."""
    servers = payload.get("mcpServers")
    if servers is None and isinstance(payload, dict):
        # bare map of name → config
        servers = payload
    if not isinstance(servers, dict) or not servers:
        raise ValueError("expected mcpServers object with at least one server")

    out: list[tuple[str, Transport, dict[str, Any]]] = []
    for name, raw in servers.items():
        if not isinstance(raw, dict):
            raise ValueError(f"server '{name}' config must be an object")
        if "url" in raw or raw.get("type") in ("http", "sse", "streamable-http", "streamable_http"):
            t_raw = str(raw.get("type") or "http").lower().replace("_", "-")
            transport: Transport = "sse" if t_raw == "sse" else "http"
            cfg = normalize_connector_config(
                transport,
                {"url": raw.get("url"), "headers": raw.get("headers") or {}},
            )
        elif "command" in raw:
            transport = "stdio"
            cfg = normalize_connector_config(
                "stdio",
                {
                    "command": raw.get("command"),
                    "args": raw.get("args") or [],
                    "env": raw.get("env") or {},
                },
            )
        else:
            raise ValueError(f"server '{name}' needs command (stdio) or url (http/sse)")
        out.append((str(name), transport, cfg))
    return out


async def list_connectors(
    session: AsyncSession,
    *,
    user_id: str,
) -> list[McpConnector]:
    result = await session.execute(
        select(McpConnectorRow)
        .where(McpConnectorRow.user_id == user_id)
        .order_by(McpConnectorRow.name)
    )
    return [_view(r) for r in result.scalars().all()]


async def get_connector(
    session: AsyncSession,
    *,
    user_id: str,
    connector_id: UUID,
) -> McpConnector | None:
    result = await session.execute(
        select(McpConnectorRow).where(
            McpConnectorRow.id == connector_id,
            McpConnectorRow.user_id == user_id,
        )
    )
    row = result.scalar_one_or_none()
    return _view(row) if row else None


async def upsert_connector(
    session: AsyncSession,
    *,
    user_id: str,
    name: str,
    transport: Transport,
    config: dict[str, Any],
    enabled: bool = True,
) -> McpConnector:
    name = name.strip()
    if not name:
        raise ValueError("connector name is required")
    cfg = normalize_connector_config(transport, config)
    result = await session.execute(
        select(McpConnectorRow).where(
            McpConnectorRow.user_id == user_id,
            McpConnectorRow.name == name,
        )
    )
    row = result.scalar_one_or_none()
    now = datetime.now(UTC)
    if row is None:
        row = McpConnectorRow(
            user_id=user_id,
            name=name,
            transport=transport,
            config=cfg,
            enabled=enabled,
            last_status="unknown",
            last_error=None,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
    else:
        row.transport = transport
        row.config = cfg
        row.enabled = enabled
        row.updated_at = now
    await session.flush()
    return _view(row)


async def update_connector(
    session: AsyncSession,
    *,
    user_id: str,
    connector_id: UUID,
    enabled: bool | None = None,
    transport: Transport | None = None,
    config: dict[str, Any] | None = None,
    name: str | None = None,
) -> McpConnector:
    result = await session.execute(
        select(McpConnectorRow).where(
            McpConnectorRow.id == connector_id,
            McpConnectorRow.user_id == user_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise KeyError("connector not found")
    if name is not None:
        n = name.strip()
        if not n:
            raise ValueError("connector name is required")
        row.name = n
    if transport is not None:
        row.transport = transport
    if config is not None:
        t: Transport = transport or row.transport  # type: ignore[assignment]
        row.config = normalize_connector_config(t, config)
    if enabled is not None:
        row.enabled = enabled
    row.updated_at = datetime.now(UTC)
    await session.flush()
    return _view(row)


async def set_connector_status(
    session: AsyncSession,
    *,
    user_id: str,
    connector_id: UUID,
    status: Literal["unknown", "ok", "error"],
    error: str | None = None,
) -> McpConnector:
    result = await session.execute(
        select(McpConnectorRow).where(
            McpConnectorRow.id == connector_id,
            McpConnectorRow.user_id == user_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise KeyError("connector not found")
    row.last_status = status
    row.last_error = error
    row.updated_at = datetime.now(UTC)
    await session.flush()
    return _view(row)


async def delete_connector(
    session: AsyncSession,
    *,
    user_id: str,
    connector_id: UUID,
) -> None:
    result = await session.execute(
        select(McpConnectorRow).where(
            McpConnectorRow.id == connector_id,
            McpConnectorRow.user_id == user_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise KeyError("connector not found")
    await session.delete(row)
    await session.flush()


async def import_connectors(
    session: AsyncSession,
    *,
    user_id: str,
    payload: dict[str, Any],
) -> list[McpConnector]:
    parsed = parse_mcp_servers_json(payload)
    out: list[McpConnector] = []
    for name, transport, cfg in parsed:
        out.append(
            await upsert_connector(
                session,
                user_id=user_id,
                name=name,
                transport=transport,
                config=cfg,
                enabled=True,
            )
        )
    return out
