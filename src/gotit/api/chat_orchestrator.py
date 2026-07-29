"""Chat orchestrator — shared A2A 接力 logic for REST and MCP.

Both the FastAPI chat route and the MCP `gotit_post_message` tool delegate here so
the agent-to-agent handoff chain stays in one place (REST ↔ MCP parity).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from gotit.api.deps import (
    SessionIdentityReader,
    SessionMemoryReader,
    SessionMessageReader,
    SessionPromptReader,
    get_model,
)
from gotit.core.agents.runtime import AgentContext, run_chat
from gotit.core.messaging import route_message
from gotit.core.models import AgentReply, ChatTurn, Message, Thread
from gotit.db import ops as day_ops

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from gotit.api.settings import Settings

MAX_A2A_TURNS = 4


def _stub_turn(agent_name: str, user_text: str, force_handoff: str | None) -> ChatTurn:
    handoff = force_handoff if force_handoff != agent_name else None
    return ChatTurn(
        text=f"[{agent_name}（无 LLM key，桩回复）] 你说了：{user_text}",
        handoff_to=handoff,
        reason=None if handoff is None else "手动转交",
    )


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
    ball = await day_ops.get_ball(session, thread.id)
    persisted_user = await day_ops.add_message(
        session,
        thread_id=thread.id,
        role="user",
        text=text,
        mentions=list(mentions),
    )

    agent_name = route_message(persisted_user, ball)
    identity_reader = SessionIdentityReader(session)
    prompt_reader = SessionPromptReader(session)

    agent_messages: list[Message] = []
    current_user_text: str = text
    current_handoff_to: str | None = handoff_to

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
            turn = await run_chat(
                ctx,
                get_model(),
                user_text=current_user_text,
                skills=skills if turn_idx == 0 else None,
                force_handoff=current_handoff_to if turn_idx == 0 else None,
            )

        agent_msg = await day_ops.add_message(
            session,
            thread_id=thread.id,
            role="agent",
            text=turn.text,
            agent_name=agent_name,
            metadata=(
                {"handoff_to": turn.handoff_to, "handoff_reason": turn.reason}
                if turn.handoff_to is not None
                else {}
            ),
        )
        agent_messages.append(agent_msg)

        await day_ops.add_memory(
            session,
            user_id=user_id,
            layer="working",
            kind="event",
            topic=thread.title,
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

    return AgentReply(user_message=persisted_user, agent_messages=agent_messages)
