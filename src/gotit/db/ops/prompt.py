"""Prompt version registration and lookup."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gotit.core.models import PromptVersion
from gotit.db.models import PromptVersionRow


def _prompt_view(row: PromptVersionRow) -> PromptVersion:
    return PromptVersion(
        id=row.id,
        agent_name=row.agent_name,
        version_label=row.version_label,
        content_hash=row.content_hash,
        system_prompt=row.system_prompt,
        config=dict(row.config or {}),
        notes=row.notes,
        created_at=row.created_at or datetime.now(UTC),
        is_active=bool(row.is_active),
    )


async def register_prompts(
    session: AsyncSession,
    versions: list[PromptVersion],
) -> list[PromptVersion]:
    """Upsert prompt versions; the latest per agent becomes the active one."""
    if not versions:
        return []
    agents = {v.agent_name for v in versions}
    for v in versions:
        existing = await session.get(PromptVersionRow, v.id)
        if existing is None:
            session.add(
                PromptVersionRow(
                    id=v.id,
                    agent_name=v.agent_name,
                    version_label=v.version_label,
                    content_hash=v.content_hash,
                    system_prompt=v.system_prompt,
                    config=dict(v.config),
                    notes=v.notes,
                    created_at=v.created_at,
                    is_active=False,
                )
            )
        else:
            existing.content_hash = v.content_hash
            existing.system_prompt = v.system_prompt
            existing.config = dict(v.config)
            existing.notes = v.notes
    await session.flush()

    stmt = select(PromptVersionRow).where(PromptVersionRow.agent_name.in_(agents))
    rows = list((await session.execute(stmt)).scalars().all())
    by_agent: dict[str, list[PromptVersionRow]] = {}
    for r in rows:
        by_agent.setdefault(r.agent_name, []).append(r)
    for agent_rows in by_agent.values():
        agent_rows.sort(
            key=lambda r: r.created_at or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
        for i, r in enumerate(agent_rows):
            r.is_active = i == 0
    await session.flush()
    return [_prompt_view(r) for r in rows]


async def get_active_prompt(
    session: AsyncSession,
    agent_name: str,
) -> PromptVersion | None:
    stmt = select(PromptVersionRow).where(
        PromptVersionRow.agent_name == agent_name,
        PromptVersionRow.is_active.is_(True),
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    return _prompt_view(row) if row is not None else None


async def list_prompts(
    session: AsyncSession,
    *,
    agent_name: str | None = None,
    active_only: bool = False,
) -> list[PromptVersion]:
    stmt = select(PromptVersionRow)
    if agent_name is not None:
        stmt = stmt.where(PromptVersionRow.agent_name == agent_name)
    if active_only:
        stmt = stmt.where(PromptVersionRow.is_active.is_(True))
    stmt = stmt.order_by(PromptVersionRow.agent_name, PromptVersionRow.created_at)
    rows = list((await session.execute(stmt)).scalars().all())
    return [_prompt_view(r) for r in rows]
