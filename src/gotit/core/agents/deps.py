"""Agent runtime dependencies (framework-free protocols).

Agents depend on these protocols; orchestration layers (api/mcp) provide
concrete implementations backed by `db.ops` and pass them as arguments to
agent runners. This keeps `gotit.core` free of FastAPI/MCP and of direct
DB session coupling.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

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


class MemoryWriter(Protocol):
    """Write access for agents — orchestration layer flushes, agents stay pure."""

    async def write_memory(
        self,
        *,
        layer: str,
        kind: str,
        content: dict[str, Any],
        topic: str | None = None,
        source: dict[str, Any] | None = None,
        expires_at: datetime | None = None,
    ) -> MemoryEntry: ...


class MessageReader(Protocol):
    """Read a thread's message history for agent context (bound to one thread)."""

    async def list_messages(self, *, limit: int = 50) -> list[Any]: ...


class PromptReader(Protocol):
    """Read the active prompt for an agent."""

    async def get_active_prompt(self, agent_name: str) -> PromptVersion | None: ...




