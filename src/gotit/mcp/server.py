from __future__ import annotations

import anyio
from mcp.server.fastmcp import FastMCP

from gotit import __version__
from gotit.core.models import CheckMode, Claim, LoopState

mcp = FastMCP("gotit")


@mcp.tool()
def gotit_health() -> dict[str, str]:
    """Return gotit-ai service health and version."""
    return {"status": "ok", "version": __version__}


@mcp.tool()
def gotit_ingest(material: str) -> dict[str, object]:
    """Ingest study material and return stub claims (Librarian not wired yet)."""
    claim = Claim(text=material.strip()[:500], source_excerpt=material[:200])
    return {
        "claims": [claim.model_dump(mode="json")],
        "state": LoopState.CLAIM.value,
        "note": "stub: claim extraction not wired yet",
    }


@mcp.tool()
def gotit_examine(claim_id: str, mode: str = CheckMode.PROBE.value) -> dict[str, object]:
    """Run an Examiner check for a claim (stub)."""
    return {
        "claim_id": claim_id,
        "mode": mode,
        "status": "stub",
        "message": "Examiner not wired yet",
    }


def main() -> None:
    # stdio transport for local OpenClaw / MCP hosts
    anyio.run(mcp.run_stdio_async)


if __name__ == "__main__":
    main()
