"""Identity layer — persistent agent personalities + rubric pinning.

Framework-free: defines the `IdentityReader` protocol agents depend on and a
helper to compose a system prompt from identity personality + pinned rubric.
DB-backed implementations live in `gotit.api.deps`.
"""

from __future__ import annotations

from typing import Protocol

from gotit.core.models import AgentIdentity


class IdentityReader(Protocol):
    """Read a persistent agent identity (personality + rubric)."""

    async def get_identity(self, agent_name: str) -> AgentIdentity | None: ...


