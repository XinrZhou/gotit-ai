from __future__ import annotations

from gotit import __version__
from gotit.mcp.app import mcp


@mcp.tool()
def gotit_health() -> dict[str, str]:
    """Return gotit-ai service health and version."""
    return {"status": "ok", "version": __version__}

