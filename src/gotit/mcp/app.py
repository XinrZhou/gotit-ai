"""FastMCP app singleton — tools register via import side effects."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("gotit")
