"""Agent runtime dependencies (framework-free protocols).

Agents depend on these protocols; orchestration layers (api/mcp) provide
concrete implementations backed by `db.ops` and pass them as arguments to
agent runners. This keeps `gotit.core` free of FastAPI/MCP and of direct
DB session coupling.
"""

from __future__ import annotations

from typing import Protocol

from gotit.core.models import MemoryEntry, PromptVersion


class MemoryReader(Protocol):
    """Read-only memory access for agents."""

    async def list_memory(
        self,
        *,
        layer: str | None = None,
        kind: str | None = None,
        topic: str | None = None,
        limit: int = 50,
    ) -> list[MemoryEntry]: ...


class PromptReader(Protocol):
    """Read the active prompt for an agent."""

    async def get_active_prompt(self, agent_name: str) -> PromptVersion | None: ...




