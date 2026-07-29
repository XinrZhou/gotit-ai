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

import json
import re
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from pydantic_ai import Agent, PromptedOutput
from pydantic_ai.exceptions import UnexpectedModelBehavior

from gotit.core.agents.deps import MemoryReader, MessageReader
from gotit.core.identity.loader import compose_system_prompt
from gotit.core.models import AgentIdentity, ChatTurn, MemoryEntry, PromptVersion

ChatAgent = Agent[Any, ChatTurn]

_VALID_HANDOFFS = frozenset({"axiom", "compass", "echo", "sage", "critic"})


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
    display_name: str,
) -> str:
    return (
        f"## 关于这位学习者的记忆\n{_format_memory(memory)}\n\n"
        f"## 之前的对话\n{_format_history(history)}\n\n"
        f"## 学习者刚说的话\n{user_text}\n\n"
        f"你现在是「{display_name}」。历史里其他同伴的发言与自我介绍与你无关，"
        f"不要照抄他们的名字或人设。\n"
        "以你的人格回应。一次只说该说的，别堆砌。\n"
        "【自我介绍】若对方说「介绍自己 / 你是谁 / 你能干嘛」之类：\n"
        f"- text 必须先自报「{display_name}」，再用角色口吻补一句你在这儿帮对方做什么；\n"
        "- 禁止反问爱好、职业、平时做什么；禁止只寒暄不介绍；\n"
        "- 一两句即可，别念职务说明书，也别复述 system 里的示例句原文。\n"
        "先在 thinking 写 1～4 句：对方真正在问什么（尤其别把「请你介绍」误判成「对方在介绍」）、"
        "该直接答还是追问、要不要转交同伴；thinking 只给学习者折叠查看，不要复述进 text。\n"
        "如果你判断这一棒该交给同伴（比如该考官出场、该让海绵宝宝整理 claim、"
        "该让派大星听你回讲），就在 handoff_to 填它的内部 agent_name "
        "(axiom/compass/echo/sage/critic)，并在 reason 写一句为什么转交；"
        "不需要转交就把 handoff_to / reason 设为 null。不要自己 @ 自己。"
        "对学习者说话时只用中文昵称，不要说 agent_name。\n"
        "请严格按 JSON 对象回复，字段：thinking, text, handoff_to, reason。"
    )


def _coerce_chat_turn(raw: str) -> ChatTurn | None:
    """Best-effort parse when the model returns JSON-ish or plain text."""
    text = raw.strip()
    if not text:
        return None
    # fenced json
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # plain prose fallback — keep conversation usable on picky gateways
        return ChatTurn(text=raw.strip())
    if not isinstance(data, dict):
        return ChatTurn(text=raw.strip())
    handoff = data.get("handoff_to")
    if handoff in ("", "null", "none", "None"):
        handoff = None
    if isinstance(handoff, str) and handoff not in _VALID_HANDOFFS:
        handoff = None
    try:
        return ChatTurn(
            thinking=data.get("thinking") or None,
            text=str(data.get("text") or raw.strip()),
            handoff_to=handoff,
            reason=data.get("reason") or None,
        )
    except ValidationError:
        return ChatTurn(text=str(data.get("text") or raw.strip()))


def _normalize_turn(turn: ChatTurn) -> ChatTurn:
    handoff = turn.handoff_to
    if handoff in ("", "null", "none"):
        handoff = None
    if handoff is not None and handoff not in _VALID_HANDOFFS:
        handoff = None
    if handoff != turn.handoff_to:
        turn = turn.model_copy(
            update={
                "handoff_to": handoff,
                "reason": None if handoff is None else turn.reason,
            }
        )
    return turn


async def run_chat(
    ctx: AgentContext,
    model: Any,
    *,
    user_text: str,
    skills: list[str] | None = None,
    skill_bodies: dict[str, str] | None = None,
    tools: list[Any] | None = None,
    toolsets: list[Any] | None = None,
    force_handoff: str | None = None,
) -> ChatTurn:
    # Chat uses personality only — examine/curate rubrics are English-first and
    # make agents introduce themselves as Compass/Axiom instead of 中文昵称.
    system_prompt = compose_system_prompt(
        ctx.identity, ctx.rubric, include_rubric=False
    )

    # On-demand skills: append requested skill bodies to the system prompt so
    # the companion can switch modes (debug / review / …) per turn.
    bodies = dict(skill_bodies or {})
    if skills:
        from gotit.core.skills import load_skill

        for name in skills:
            if name in bodies:
                continue
            body = load_skill(name)
            if body:
                bodies[name] = body
    for _name, body in bodies.items():
        if body:
            system_prompt = f"{system_prompt}\n\n---\n\n{body}".strip("\n")

    # PromptedOutput (JSON-in-prompt) is more reliable than tool-calling structured
    # output on many OpenAI-compatible gateways (e.g. GLM).
    agent_kwargs: dict[str, Any] = {
        "output_type": PromptedOutput(ChatTurn),
        "system_prompt": system_prompt,
        "name": ctx.identity.agent_name,
        "retries": 2,
    }
    # Agent-as-tool: optionally pass callable tools / MCP toolsets the agent may
    # invoke during the run. Only exercised under a real LLM; stubbed paths pass none.
    if tools:
        agent_kwargs["tools"] = tools
    if toolsets:
        agent_kwargs["toolsets"] = toolsets
    agent: ChatAgent = Agent(model, **agent_kwargs)

    history = await ctx.messages.list_messages(limit=20)
    memory = await ctx.memory.list_memory(layer="long", limit=10)
    prompt = build_chat_prompt(
        user_text=user_text,
        history=history,
        memory=memory,
        display_name=ctx.identity.display_name,
    )
    try:
        result = await agent.run(prompt)
        turn = _normalize_turn(result.output)
    except UnexpectedModelBehavior as exc:
        # Recover usable reply text from the model body when structured parse fails.
        recovered = _coerce_chat_turn(exc.body or "") if exc.body else None
        if recovered is None or not recovered.text.strip():
            raise
        turn = _normalize_turn(recovered)
    # Manual/bypass handoff overrides the agent's own decision (tests / manual
    # turn-taking without an LLM). Self-handoff is treated as no handoff.
    if force_handoff is not None and force_handoff != ctx.identity.agent_name:
        turn = turn.model_copy(update={"handoff_to": force_handoff})
    if turn.handoff_to == ctx.identity.agent_name:
        turn = turn.model_copy(update={"handoff_to": None})
    return turn
