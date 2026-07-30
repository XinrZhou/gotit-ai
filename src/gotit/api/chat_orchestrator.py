"""Chat orchestrator — shared A2A 接力 logic for REST and MCP.

Both the FastAPI chat route and the MCP `gotit_post_message` tool delegate here so
the agent-to-agent handoff chain stays in one place (REST ↔ MCP parity).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from gotit.api.deps import (
    SessionIdentityReader,
    SessionMemoryReader,
    SessionMessageReader,
    SessionPromptReader,
    get_model,
)
from gotit.core.agents.runtime import (
    AgentContext,
    format_plan_markdown_list,
    format_today_plan_brief,
    run_chat,
)
from gotit.core.messaging import route_message
from gotit.core.models import AgentReply, ChatTurn, Message, Thread
from gotit.db import ops as day_ops

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from gotit.api.settings import Settings

MAX_A2A_TURNS = 4
_PLAN_TZ = ZoneInfo("Asia/Shanghai")


def _learner_today() -> date:
    return datetime.now(_PLAN_TZ).date()


def _stub_turn(agent_name: str, user_text: str, force_handoff: str | None) -> ChatTurn:
    handoff = force_handoff if force_handoff != agent_name else None
    return ChatTurn(
        thinking=None,
        text=f"[{agent_name}（无 LLM key，桩回复）] 你说了：{user_text}",
        handoff_to=handoff,
        reason=None if handoff is None else "手动转交",
    )


def _agent_metadata(turn: ChatTurn) -> dict[str, object]:
    meta: dict[str, object] = {}
    if turn.thinking:
        meta["thinking"] = turn.thinking
    if turn.handoff_to is not None:
        meta["handoff_to"] = turn.handoff_to
        meta["handoff_reason"] = turn.reason
    return meta


async def post_message_chain(
    session: AsyncSession,
    *,
    settings: Settings,
    user_id: str,
    thread: Thread,
    text: str,
    mentions: list[str],
    skills: list[str],
    handoff_to: str | None,
) -> AgentReply:
    """Run one user message through the A2A 接力 chain and persist every reply."""
    from gotit.api.mcp_toolsets import entered_toolsets

    prior_user_count = await day_ops.count_user_messages(session, thread.id)
    ball = await day_ops.get_ball(session, thread.id)
    persisted_user = await day_ops.add_message(
        session,
        thread_id=thread.id,
        role="user",
        text=text,
        mentions=list(mentions),
    )

    updated_thread: Thread | None = None
    if prior_user_count == 0:
        title = day_ops.derive_thread_title(text)
        if title != thread.title:
            updated_thread = await day_ops.update_thread_title(
                session, thread.id, title=title
            )

    agent_name = route_message(persisted_user, ball)
    identity_reader = SessionIdentityReader(session)
    prompt_reader = SessionPromptReader(session)

    skill_bodies: dict[str, str] = {}
    for name in skills:
        body = await day_ops.resolve_skill_body(session, user_id=user_id, name=name)
        if body:
            skill_bodies[name] = body

    connectors = await day_ops.list_connectors(session, user_id=user_id)
    enabled_connectors = [c for c in connectors if c.enabled]

    today = _learner_today()
    plan = await day_ops.get_plan(session, today, user_id=user_id)
    plan_markdown_list = format_plan_markdown_list(plan)
    today_plan_brief = format_today_plan_brief(
        plan,
        include_list=plan_markdown_list is None,
    )

    agent_messages: list[Message] = []
    current_user_text: str = text
    current_handoff_to: str | None = handoff_to

    async with entered_toolsets(enabled_connectors) as toolsets:
        # --- A2A 链式接力：首棒回复后可 handoff 给同伴，同伴再回复，
        # 直到无 handoff 或达上限。 ---
        for turn_idx in range(MAX_A2A_TURNS):
            identity = await identity_reader.get_identity(agent_name)
            if identity is None:
                raise KeyError(f"agent identity '{agent_name}' not seeded")
            rubric = await prompt_reader.get_active_prompt(agent_name)

            if not settings.llm_api_key:
                turn = _stub_turn(agent_name, current_user_text, current_handoff_to)
            else:
                ctx = AgentContext(
                    identity=identity,
                    rubric=rubric,
                    memory=SessionMemoryReader(session, user_id=user_id),
                    messages=SessionMessageReader(session, thread_id=thread.id),
                )
                try:
                    turn = await run_chat(
                        ctx,
                        get_model(),
                        user_text=current_user_text,
                        skill_bodies=skill_bodies if turn_idx == 0 else None,
                        toolsets=toolsets or None,
                        force_handoff=current_handoff_to if turn_idx == 0 else None,
                        today_plan_brief=today_plan_brief,
                        plan_markdown_list=plan_markdown_list,
                    )
                except Exception as exc:
                    # Keep the user turn; surface failure as an in-thread agent reply
                    # so the UI never has to roll back the optimistic send.
                    detail = str(exc).split("\n", 1)[0][:240]
                    err_text = (
                        f"搭子暂时没回上（{type(exc).__name__}: {detail}）"
                    )
                    agent_msg = await day_ops.add_message(
                        session,
                        thread_id=thread.id,
                        role="agent",
                        text=err_text,
                        agent_name=agent_name,
                        metadata={
                            "error": True,
                            "error_type": type(exc).__name__,
                        },
                    )
                    agent_messages.append(agent_msg)
                    return AgentReply(
                        user_message=persisted_user,
                        agent_messages=agent_messages,
                        thread=updated_thread,
                    )

            agent_msg = await day_ops.add_message(
                session,
                thread_id=thread.id,
                role="agent",
                text=turn.text,
                agent_name=agent_name,
                metadata=_agent_metadata(turn),
            )
            agent_messages.append(agent_msg)

            await day_ops.add_memory(
                session,
                user_id=user_id,
                layer="working",
                kind="event",
                topic=(updated_thread.title if updated_thread else thread.title),
                content={"agent": agent_name, "user": text, "reply": turn.text},
                source={"thread_id": str(thread.id)},
            )

            next_holder = turn.handoff_to
            if next_holder is None or next_holder == agent_name:
                break
            if turn_idx + 1 >= MAX_A2A_TURNS:
                await day_ops.add_message(
                    session,
                    thread_id=thread.id,
                    role="system",
                    text=f"接力上限（{MAX_A2A_TURNS}），已截断。",
                )
                break
            target_identity = await identity_reader.get_identity(next_holder)
            if target_identity is None:
                await day_ops.add_message(
                    session,
                    thread_id=thread.id,
                    role="system",
                    text=f"未知 agent「{next_holder}」，转交忽略。",
                )
                break

            await day_ops.set_ball(
                session,
                thread_id=thread.id,
                holder=next_holder,
                stage="chat",
                context={"from": agent_name, "reason": turn.reason},
            )
            reason_block = (
                f"## 转交上下文\n{agent_name} 把对话转给你"
                + (f"，理由：{turn.reason}" if turn.reason else "")
                + f"\n## 学习者的话\n{text}"
            )
            current_user_text = reason_block
            agent_name = next_holder
            current_handoff_to = None

    return AgentReply(
        user_message=persisted_user,
        agent_messages=agent_messages,
        thread=updated_thread,
    )
