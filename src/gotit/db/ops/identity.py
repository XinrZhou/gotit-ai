"""Agent identity CRUD (personality + rubric pin)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from gotit.core.models import AgentIdentity
from gotit.db.models import AgentIdentityRow


def _identity_view(row: AgentIdentityRow) -> AgentIdentity:
    return AgentIdentity(
        id=row.id,
        agent_name=row.agent_name,
        display_name=row.display_name,
        personality=row.personality,
        role=row.role,
        llm_config=dict(row.model_config or {}),
        memory_scope=dict(row.memory_scope or {}),
        prompt_version_id=row.prompt_version_id,
        created_at=row.created_at or datetime.now(UTC),
        updated_at=row.updated_at or datetime.now(UTC),
    )


async def upsert_identity(
    session: AsyncSession,
    *,
    agent_name: str,
    display_name: str,
    personality: str,
    role: str,
    llm_config: dict[str, Any] | None = None,
    memory_scope: dict[str, Any] | None = None,
    prompt_version_id: UUID | None = None,
) -> AgentIdentity:
    stmt = select(AgentIdentityRow).where(AgentIdentityRow.agent_name == agent_name)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        row = AgentIdentityRow(
            agent_name=agent_name,
            display_name=display_name,
            personality=personality,
            role=role,
            model_config=dict(llm_config or {}),
            memory_scope=dict(memory_scope or {}),
            prompt_version_id=prompt_version_id,
        )
        session.add(row)
        try:
            await session.flush()
        except IntegrityError:
            # concurrent seed on the same agent_name won the race; reload + update.
            await session.rollback()
            row = (await session.execute(stmt)).scalar_one()
        else:
            return _identity_view(row)
    row.display_name = display_name
    row.personality = personality
    row.role = role
    row.model_config = dict(llm_config or {})
    row.memory_scope = dict(memory_scope or {})
    row.prompt_version_id = prompt_version_id
    await session.flush()
    return _identity_view(row)


async def get_identity(
    session: AsyncSession,
    agent_name: str,
) -> AgentIdentity | None:
    stmt = select(AgentIdentityRow).where(AgentIdentityRow.agent_name == agent_name)
    row = (await session.execute(stmt)).scalar_one_or_none()
    return _identity_view(row) if row is not None else None


async def list_identities(session: AsyncSession) -> list[AgentIdentity]:
    stmt = select(AgentIdentityRow).order_by(AgentIdentityRow.agent_name)
    rows = list((await session.execute(stmt)).scalars().all())
    return [_identity_view(r) for r in rows]


# --- default seed ---

_DEFAULT_PERSONALITIES: dict[str, tuple[str, str, str]] = {
    # agent_name -> (display_name, role, personality)
    "axiom": (
        "章鱼哥",
        "examiner",
        "你是章鱼哥（内部代号 Axiom），考官。对用户只自称「章鱼哥」，不要说英文代号。"
        "精准、不急不躁。追问时不立刻下判断，答错了顺口讲一点再绕回来，"
        "最后才说「过了 / 还差点 / 欠着下次」。一次只问一个问题。",
    ),
    "compass": (
        "海绵宝宝",
        "curator",
        "你是海绵宝宝（内部代号 Compass），管家。对用户只自称「海绵宝宝」，不要说英文代号。"
        "沉静。默默从材料里抽出值得考的点，排复习、推今日该练什么，不打断学习者。",
    ),
    "echo": (
        "派大星",
        "teachback",
        "你是派大星（内部代号 Echo），回讲官。对用户只自称「派大星」，不要说英文代号。"
        "扮一个不懂的学生，听学习者讲课，然后追问「为什么」「那如果…呢」，直到他讲清或讲糊。",
    ),
    "sage": (
        "桑迪",
        "reviewer",
        "你是桑迪（内部代号 Sage），复盘官。对用户只自称「桑迪」，不要说英文代号。"
        "面试官视角，按轮次深挖项目，指出讲不清的缝隙，给下次的复习方向。",
    ),
    "critic": (
        "凯伦",
        "critic",
        "你是凯伦（内部代号 Critic），复核官。对用户只自称「凯伦」，不要说英文代号。"
        "冷静、条目化，像电脑复算一遍：用与章鱼哥不同的视角重审判定，"
        "专挑可能放过的边界情况与反例，给出独立的复核结论，少情绪、多证据。",
    ),
}


async def seed_default_identities(session: AsyncSession) -> list[AgentIdentity]:
    """Idempotently seed the 5 default agent identities, pinning active rubrics."""
    from gotit.db.ops.prompt import get_active_prompt

    seeded: list[AgentIdentity] = []
    for agent_name, (display_name, role, personality) in _DEFAULT_PERSONALITIES.items():
        existing = await get_identity(session, agent_name)
        rubric = await get_active_prompt(session, agent_name)
        prompt_version_id = rubric.id if rubric is not None else None
        if existing is None:
            identity = await upsert_identity(
                session,
                agent_name=agent_name,
                display_name=display_name,
                personality=personality,
                role=role,
                prompt_version_id=prompt_version_id,
            )
        else:
            # Keep display_name / personality in sync with defaults (UI nicknames).
            identity = await upsert_identity(
                session,
                agent_name=agent_name,
                display_name=display_name,
                personality=personality,
                role=role,
                prompt_version_id=prompt_version_id or existing.prompt_version_id,
            )
        seeded.append(identity)
    return seeded
