"""Orchestration-side wiring: shared model instance built from settings.

`gotit.core` stays framework-free; this module is the seam that reads settings
and hands a configured model to agents.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_ai.models.openai import OpenAIChatModel
from sqlalchemy.ext.asyncio import AsyncSession

from gotit.api.settings import get_settings
from gotit.core.agents.llm import build_model
from gotit.core.models import MemoryEntry, PromptVersion
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


class SessionPromptReader:
    """`PromptReader` backed by an `AsyncSession`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_prompt(self, agent_name: str) -> PromptVersion | None:
        return await day_ops.get_active_prompt(self._session, agent_name)

