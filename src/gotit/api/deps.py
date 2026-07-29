"""Orchestration-side wiring: shared model instance built from settings.

`gotit.core` stays framework-free; this module is the seam that reads settings
and hands a configured model to agents.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any
from uuid import UUID

from pydantic_ai.models.openai import OpenAIChatModel
from sqlalchemy.ext.asyncio import AsyncSession

from gotit.api.settings import get_settings
from gotit.core.agents.llm import build_model
from gotit.core.models import AgentIdentity, MemoryEntry, PromptVersion
from gotit.db import ops as day_ops


@lru_cache(maxsize=1)
def get_model() -> OpenAIChatModel:
    settings = get_settings()
    return build_model(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model_name=settings.llm_model,
    )


class SessionMemoryReader:
    """`MemoryReader` backed by an `AsyncSession` + user id."""

    def __init__(self, session: AsyncSession, *, user_id: str) -> None:
        self._session = session
        self._user_id = user_id

    async def list_memory(
        self,
        *,
        layer: str | None = None,
        kind: str | None = None,
        topic: str | None = None,
        limit: int = 50,
    ) -> list[MemoryEntry]:
        return await day_ops.list_memory(
            self._session,
            user_id=self._user_id,
            layer=layer,
            kind=kind,
            topic=topic,
            limit=limit,
        )


class SessionMemoryWriter:
    """`MemoryWriter` backed by an `AsyncSession` + user id."""

    def __init__(self, session: AsyncSession, *, user_id: str) -> None:
        self._session = session
        self._user_id = user_id

    async def write_memory(
        self,
        *,
        layer: str,
        kind: str,
        content: dict[str, Any],
        topic: str | None = None,
        source: dict[str, Any] | None = None,
        expires_at: Any | None = None,
    ) -> MemoryEntry:
        return await day_ops.add_memory(
            self._session,
            user_id=self._user_id,
            layer=layer,
            kind=kind,
            content=content,
            topic=topic,
            source=source,
            expires_at=expires_at,
        )


class SessionPromptReader:
    """`PromptReader` backed by an `AsyncSession`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_prompt(self, agent_name: str) -> PromptVersion | None:
        return await day_ops.get_active_prompt(self._session, agent_name)


class SessionIdentityReader:
    """`IdentityReader` backed by an `AsyncSession`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_identity(self, agent_name: str) -> AgentIdentity | None:
        return await day_ops.get_identity(self._session, agent_name)


class SessionMessageReader:
    """`MessageReader` bound to one thread."""

    def __init__(self, session: AsyncSession, *, thread_id: UUID) -> None:
        self._session = session
        self._thread_id = thread_id

    async def list_messages(self, *, limit: int = 50) -> list[Any]:
        return await day_ops.list_messages(
            self._session, thread_id=self._thread_id, limit=limit
        )


