"""Build Pydantic AI MCPToolsets from stored connector configs.

Lives in api/ (not core) because it depends on FastMCP / pydantic_ai.mcp.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

from gotit.core.models import McpConnector

logger = logging.getLogger(__name__)


def build_mcp_toolset(connector: McpConnector) -> Any:
    """Construct an MCPToolset for one connector (not yet entered)."""
    from fastmcp.client import Client
    from fastmcp.client.transports import (
        SSETransport,
        StdioTransport,
        StreamableHttpTransport,
    )
    from pydantic_ai.mcp import MCPToolset

    cfg = connector.config or {}
    if connector.transport == "stdio":
        transport: Any = StdioTransport(
            command=str(cfg["command"]),
            args=[str(a) for a in (cfg.get("args") or [])],
            env={str(k): str(v) for k, v in (cfg.get("env") or {}).items()} or None,
        )
        client = Client(transport)
        return MCPToolset(client, id=connector.name)
    url = str(cfg["url"])
    headers = {str(k): str(v) for k, v in (cfg.get("headers") or {}).items()} or None
    if connector.transport == "sse":
        client = Client(SSETransport(url, headers=headers))
    else:
        client = Client(StreamableHttpTransport(url, headers=headers))
    return MCPToolset(client, id=connector.name)


@asynccontextmanager
async def entered_toolsets(
    connectors: list[McpConnector],
) -> AsyncIterator[list[Any]]:
    """Enter enabled connectors as toolsets; skip failures (log + continue)."""
    stack = AsyncExitStack()
    await stack.__aenter__()
    toolsets: list[Any] = []
    try:
        for conn in connectors:
            if not conn.enabled:
                continue
            try:
                ts = build_mcp_toolset(conn)
                entered = await stack.enter_async_context(ts)
                toolsets.append(entered)
            except Exception as exc:  # noqa: BLE001 — never block chat on one MCP
                logger.warning(
                    "mcp connector %s failed to start: %s", conn.name, exc
                )
        yield toolsets
    finally:
        await stack.__aexit__(None, None, None)


async def probe_connector(connector: McpConnector) -> tuple[bool, str | None]:
    """Try to connect and list tools; return (ok, error_message)."""
    try:
        ts = build_mcp_toolset(connector)
        async with ts:
            await ts.list_tools()
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:500]
