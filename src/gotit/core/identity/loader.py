"""Compose a system prompt from agent identity + pinned rubric."""

from __future__ import annotations

from gotit.core.models import AgentIdentity, PromptVersion


def compose_system_prompt(
    identity: AgentIdentity,
    rubric: PromptVersion | None = None,
) -> str:
    """Personality first, then the rubric (stable judgement criteria)."""
    parts: list[str] = []
    if identity.personality.strip():
        parts.append(identity.personality.strip())
    if rubric is not None and rubric.system_prompt.strip():
        parts.append(rubric.system_prompt.strip())
    return "\n\n---\n\n".join(parts) if parts else ""
