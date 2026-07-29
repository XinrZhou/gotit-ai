"""Agent runtime — conversational runner over identity + memory + thread history.

The existing `axiom/compass/echo/sage` modules are structured-output agents
(examine/teach/etc.). This module adds a **conversational** runner used by the
chat surface: it composes a system prompt from a persistent identity
(personality + pinned rubric), injects thread history + relevant memory, and
returns free-form text.

Framework-free: depends only on `pydantic_ai` (a core-allowed library) and the
`MemoryReader` / `MessageReader` / `IdentityReader` protocols. Orchestration
layers pass a concrete model + protocol implementations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic_ai import Agent

from gotit.core.agents.deps import MemoryReader, MessageReader
from gotit.core.identity.loader import compose_system_prompt
from gotit.core.models import AgentIdentity, ChatTurn, MemoryEntry, PromptVersion

ChatAgent = Agent[Any, ChatTurn]


@dataclass
class AgentContext:
    identity: AgentIdentity
    rubric: PromptVersion | None
    memory: MemoryReader
    messages: MessageReader


def _format_history(history: list[Any]) -> str:
    if not history:
        return "(对话刚开始)"
    lines: list[str] = []
    for m in history:
        who = m.agent_name or ("你" if m.role == "user" else "系统")
        lines.append(f"{who}: {m.text}")
    return "\n".join(lines)


def _format_memory(memory: list[MemoryEntry]) -> str:
    if not memory:
        return "(还没有关于这位学习者的记忆)"
    return "\n".join(f"- [{m.kind}] {m.topic or '-'}: {m.content}" for m in memory[:10])


def build_chat_prompt(
    *,
    user_text: str,
    history: list[Any],
    memory: list[MemoryEntry],
) -> str:
    return (
        f"## 关于这位学习者的记忆\n{_format_memory(memory)}\n\n"
        f"## 之前的对话\n{_format_history(history)}\n\n"
        f"## 学习者刚说的话\n{user_text}\n\n"
        "以你的人格回应。一次只说该说的，别堆砌。\n"
        "如果你判断这一棒该交给同伴（比如该考官出场、该让 compass 整理 claim、"
        "该让 echo 听你回讲），就在 handoff_to 填它的 agent_name "
        "(axiom/compass/echo/sage/critic)，并在 reason 写一句为什么转交；"
        "不需要转交就留空。不要自己 @ 自己。"
    )


async def run_chat(
    ctx: AgentContext,
    model: Any,
    *,
    user_text: str,
    skills: list[str] | None = None,
    tools: list[Any] | None = None,
    force_handoff: str | None = None,
) -> ChatTurn:
    system_prompt = compose_system_prompt(ctx.identity, ctx.rubric)

    # On-demand skills: append requested skill bodies to the system prompt so
    # the companion can switch modes (debug / review / …) per turn.
    if skills:
        from gotit.core.skills import load_skill

        for name in skills:
            body = load_skill(name)
            if body:
                system_prompt = f"{system_prompt}\n\n---\n\n{body}".strip("\n")

    agent_kwargs: dict[str, Any] = {
        "output_type": ChatTurn,
        "system_prompt": system_prompt,
        "name": ctx.identity.agent_name,
    }
    # Agent-as-tool: optionally pass callable tools the agent may invoke during
    # the run (e.g. gotit's own ingest/examine ops exposed as agent tools). Only
    # exercised under a real LLM; stubbed paths pass no tools.
    if tools:
        agent_kwargs["tools"] = tools
    agent: ChatAgent = Agent(model, **agent_kwargs)

    history = await ctx.messages.list_messages(limit=20)
    memory = await ctx.memory.list_memory(layer="long", limit=10)
    prompt = build_chat_prompt(user_text=user_text, history=history, memory=memory)
    result = await agent.run(prompt)
    turn = result.output
    # Manual/bypass handoff overrides the agent's own decision (tests / manual
    # turn-taking without an LLM). Self-handoff is treated as no handoff.
    if force_handoff is not None and force_handoff != ctx.identity.agent_name:
        turn = turn.model_copy(update={"handoff_to": force_handoff})
    if turn.handoff_to == ctx.identity.agent_name:
        turn = turn.model_copy(update={"handoff_to": None})
    return turn
