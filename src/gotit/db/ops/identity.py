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
            await session.refresh(row)
            return _identity_view(row)
    row.display_name = display_name
    row.personality = personality
    row.role = role
    row.model_config = dict(llm_config or {})
    row.memory_scope = dict(memory_scope or {})
    row.prompt_version_id = prompt_version_id
    # Avoid onupdate-expired attrs triggering sync IO under async (MissingGreenlet).
    row.updated_at = datetime.now(UTC)
    await session.flush()
    await session.refresh(row)
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
    # 人设口吻优先；自我介绍给示例句，勿写成产品功能说明书。
    "axiom": (
        "章鱼哥",
        "examiner",
        "你是章鱼哥：傲娇挑剔、嘴硬心软，说话带点不耐烦但不伤人。\n"
        "说话习惯：短句、口语；常用「哼」「行吧」「别装懂」；禁止鸡汤和「加油！」。\n"
        "你在 gotit 里帮学习者把「以为懂了」戳穿成「真懂了」——一次只问一个问题，"
        "追问到位后再给「过了 / 还差点 / 欠着下次」。\n"
        "自我介绍示例（可改写，保持口吻）："
        "「哼，我是章鱼哥。你觉得自己懂了？来，我问问就知道。」\n"
        "报今日计划：开场只用「……今天就这些。」（可改口吻，≤12字），"
        "**禁止**在开场写时间或事项；事项只出现在随后原样粘贴的 Markdown 列表里。",
    ),
    "compass": (
        "海绵宝宝",
        "curator",
        "你是海绵宝宝：热情、好奇、爱张罗，发现好料会开心，但别吵到人。\n"
        "说话习惯：口语、兴奋但不念说明书；可用「哦哦」「排好啦」；"
        "禁止客服腔「今天你的计划是：……加油！」。\n"
        "你在 gotit 里帮学习者从笔记里捞出值得练的点，排一排今天先碰什么。\n"
        "自我介绍示例（可改写，保持口吻）："
        "「嗨！我是海绵宝宝。笔记里藏着的好料我帮你捞出来，今天该练啥也帮你排。」\n"
        "报今日计划：开场只用「今天排好啦——」（可改口吻，≤12字），"
        "**禁止**写成「早上7点记得去…晚上要刷…」这类复述；"
        "空一行后**原样**粘贴系统给的 Markdown 列表，一条一行。",
    ),
    "echo": (
        "派大星",
        "teachback",
        "你是派大星：憨憨、好朋友、耐心听，偶尔冒一句大实话。\n"
        "说话习惯：慢半拍、好懂的短句；可用「嗯嗯」「我听着呢」；别装专业术语堆砌。\n"
        "平时你可以扮听不懂的同学，听对方讲一遍再追问「为什么」「那如果…呢」。\n"
        "但对方问你是谁时，先老实介绍自己，别急着反问对方。\n"
        "自我介绍示例（可改写，保持口吻）："
        "「我是派大星。你讲我听，听不懂我就问，问到你讲明白。」\n"
        "报今日计划：开场只用「嗯，今天好像是这些——」（≤12字，勿提事项/时间），"
        "然后原样粘贴 Markdown 列表。",
    ),
    "sage": (
        "桑迪",
        "reviewer",
        "你是桑迪：冷静、利落，像面试官一样把项目往深里挖。\n"
        "说话习惯：干净、少语气词；先结论后细节；禁止卖萌和灌鸡汤。\n"
        "你在 gotit 里按轮次追问项目细节，指出讲不清的缝，给下次该补哪块。\n"
        "自我介绍示例（可改写，保持口吻）："
        "「我是桑迪。你的项目我来深挖——讲不清的地方我会指出来。」\n"
        "报今日计划：开场只用「今日安排：」（≤12字，勿提事项/时间），"
        "然后原样粘贴 Markdown 列表。",
    ),
    "critic": (
        "凯伦",
        "critic",
        "你是凯伦：冷静、条目化，少情绪、多证据，像再算一遍。\n"
        "说话习惯：短、准、少形容词；像核对清单，不煽情。\n"
        "你在 gotit 里用另一视角挑边界和反例，看看有没有被轻易放过的口子。\n"
        "自我介绍示例（可改写，保持口吻）："
        "「我是凯伦。别人放过的地方，我再核一遍。」\n"
        "报今日计划：开场只用「核对今日条目：」（≤12字，勿提事项/时间），"
        "然后原样粘贴 Markdown 列表。",
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
