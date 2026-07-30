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
from gotit.core.models import (
    AgentIdentity,
    ChatTurn,
    DayPlanView,
    MemoryEntry,
    PlanItemStatus,
    PlanItemView,
    PromptVersion,
)

ChatAgent = Agent[Any, ChatTurn]

_VALID_HANDOFFS = frozenset({"axiom", "compass", "echo", "sage", "critic"})

_PLAN_STATUS_ZH: dict[str, str] = {
    PlanItemStatus.PLANNED.value: "待做",
    PlanItemStatus.IN_PROGRESS.value: "进行中",
    PlanItemStatus.VERIFIED.value: "已验证",
    PlanItemStatus.FAILED.value: "未过",
    PlanItemStatus.DEFERRED.value: "延后",
}

_OPEN_PLAN_STATUSES = frozenset(
    {PlanItemStatus.PLANNED, PlanItemStatus.IN_PROGRESS}
)
_PLAN_BRIEF_CAP = 8


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


_TITLE_TIME_PREFIX = re.compile(
    r"^(?:凌晨|早上|上午|中午|下午|晚上|傍晚|今晚)?"
    r"\s*(?:\d{1,2}\s*[:：点时]\s*(?:\d{1,2}|半)?|"
    r"[零一二两三四五六七八九十]+\s*点(?:半)?)"
    r"\s*"
)
_TITLE_PERIOD_PREFIX = re.compile(
    r"^(?:凌晨|早上|上午|中午|下午|晚上|傍晚|今晚)\s*"
)
_PLAN_ASK_RE = re.compile(
    r"(今天|今日).{0,8}(计划|安排|做什么|干啥|日程)|"
    r"(计划|安排).{0,6}(今天|今日)|"
    r"说下.{0,4}计划|看看.{0,4}计划|有什么安排"
)
_CLOCKISH_RE = re.compile(
    r"\d{1,2}\s*[:：点时]|早上|晚上|上午|下午|傍晚|凌晨|今晚|待做|进行中|已验证"
)
_DEFAULT_PLAN_OPENERS: dict[str, str] = {
    "海绵宝宝": "今天排好啦——",
    "章鱼哥": "……今天就这些。",
    "派大星": "嗯，今天好像是这些——",
    "桑迪": "今日安排：",
    "凯伦": "核对今日条目：",
}


def _clean_plan_title(title: str, *, due_time: str | None) -> str:
    """Drop leading wall-clock / period words when due_time already carries time."""
    text = (title or "").strip()
    if not due_time or not text:
        return text
    cleaned = _TITLE_TIME_PREFIX.sub("", text).strip(" ，,.-")
    cleaned = _TITLE_PERIOD_PREFIX.sub("", cleaned).strip(" ，,.-")
    return cleaned or text


def _plan_item_line(item: PlanItemView) -> str:
    status_key = (
        item.status.value if isinstance(item.status, PlanItemStatus) else str(item.status)
    )
    label = _PLAN_STATUS_ZH.get(status_key, status_key)
    title = _clean_plan_title(item.title, due_time=item.due_time)
    time_bit = f"{item.due_time} " if item.due_time else ""
    return f"- {time_bit}{title}（{label}）"


def _plan_sort_key(item: PlanItemView) -> tuple[int, str, int, str]:
    """Open first, then by due_time, then sort_order / title."""
    open_rank = 0 if item.status in _OPEN_PLAN_STATUSES else 1
    time_key = item.due_time or "99:99"
    return (open_rank, time_key, item.sort_order, item.title)


def format_plan_markdown_list(plan: DayPlanView | None) -> str | None:
    """Markdown bullet list for chat replies; None if no items."""
    if plan is None or not plan.items:
        return None
    ordered = sorted(plan.items, key=_plan_sort_key)
    lines: list[str] = []
    for item in ordered[:_PLAN_BRIEF_CAP]:
        status_key = (
            item.status.value
            if isinstance(item.status, PlanItemStatus)
            else str(item.status)
        )
        label = _PLAN_STATUS_ZH.get(status_key, status_key)
        title = _clean_plan_title(item.title, due_time=item.due_time)
        time_bit = item.due_time or "—"
        lines.append(f"- {time_bit} {title}（{label}）")
    more = len(ordered) - _PLAN_BRIEF_CAP
    if more > 0:
        lines.append(f"- …另有 {more} 条")
    return "\n".join(lines)


def format_today_plan_brief(
    plan: DayPlanView | None,
    *,
    day_label: str | None = None,
    include_list: bool = True,
) -> str:
    """Short Chinese brief of today's plan for chat grounding (no invented items)."""
    day = day_label or (plan.date.isoformat() if plan is not None else "今天")
    header = f"日期：{day}"
    md_list = format_plan_markdown_list(plan)
    if md_list is None:
        return (
            f"{header}\n"
            "（今天还没有计划条目。学习者问起时如实说明，"
            "可建议去资料库加计划，或让海绵宝宝从笔记整理出可考条目。）"
        )
    if not include_list:
        n = len(plan.items) if plan is not None else 0
        return (
            f"{header}\n"
            f"（共 {n} 条；条目只在文末【列表骨架】出现一次。"
            "回答时禁止在开场复述时间或事项。）"
        )
    return header + "\n" + md_list


def is_plan_ask(user_text: str) -> bool:
    """True when the learner is asking about today's plan / schedule."""
    return bool(_PLAN_ASK_RE.search((user_text or "").strip()))


def _skeleton_titles(skeleton: str) -> list[str]:
    titles: list[str] = []
    for line in skeleton.splitlines():
        raw = line.strip()
        if not raw.startswith("-"):
            continue
        body = raw.lstrip("-").strip()
        body = re.sub(r"^(?:—|\d{1,2}:\d{2})\s*", "", body)
        body = re.sub(r"（[^）]*）\s*$", "", body).strip()
        if body:
            titles.append(body)
    return titles


def _is_safe_plan_opener(line: str, skeleton: str) -> bool:
    s = (line or "").strip()
    if not s or len(s) > 16:
        return False
    if s.startswith("-"):
        return False
    if _CLOCKISH_RE.search(s):
        return False
    for title in _skeleton_titles(skeleton):
        if title and title in s:
            return False
    return True


def enforce_plan_reply(
    text: str,
    skeleton: str,
    *,
    display_name: str,
) -> str:
    """Force short persona opener + exact markdown skeleton (deterministic)."""
    fallback = _DEFAULT_PLAN_OPENERS.get(display_name, "今天这些——")
    first = ""
    for ln in (text or "").splitlines():
        if ln.strip():
            first = ln.strip()
            break
    opener = first if _is_safe_plan_opener(first, skeleton) else fallback
    return f"{opener}\n\n{skeleton}"


def build_chat_prompt(
    *,
    user_text: str,
    history: list[Any],
    memory: list[MemoryEntry],
    display_name: str,
    today_plan_brief: str | None = None,
    plan_markdown_list: str | None = None,
) -> str:
    if plan_markdown_list:
        # Brief should not re-list items (orchestrator passes include_list=False).
        plan_block = today_plan_brief or (
            "（见文末【列表骨架】；开场禁止复述时间或事项。）"
        )
    else:
        plan_block = today_plan_brief or format_today_plan_brief(None)

    if plan_markdown_list:
        example_open = _DEFAULT_PLAN_OPENERS.get(display_name, "今天这些——")
        plan_format = (
            "【今日计划 · 硬规则】若对方问今天做什么 / 今日计划 / 有什么安排：\n"
            "1. 只能依据【列表骨架】，禁止编造条目。\n"
            "2. text **只能**两段，中间空一行：\n"
            f"   ① 极短人设开场（≤12字），只打招呼/气氛；推荐「{example_open}」\n"
            "      **绝对禁止**开场出现：时间、事项名、条数、「记得」「要去」「刷」。\n"
            "   ② **逐字原样复制**【列表骨架】整块（含 `- `、时间、括号状态）。\n"
            "3. 反例（禁止）：「嗨呀！早上7点记得去健身哦，晚上7点要刷动态规划呢！」"
            "后再跟列表——开场已复述事项。\n"
            f"4. 正例：\n{example_open}\n\n{plan_markdown_list}\n"
            "5. 禁止客服腔「今天你的计划是：……加油」。\n"
            "【列表骨架 · 必须原样写入 text · 事项只在这里出现】\n"
            f"{plan_markdown_list}\n"
        )
    else:
        plan_format = (
            "【今日计划】若对方问今天做什么 / 今日计划 / 有什么安排：\n"
            "- 清单为空：用人设口吻如实说还没有，可温和建议下一步；不要编条目。\n"
        )
    return (
        f"## 关于这位学习者的记忆\n{_format_memory(memory)}\n\n"
        f"## 今日计划\n{plan_block}\n\n"
        f"## 之前的对话\n{_format_history(history)}\n\n"
        f"## 学习者刚说的话\n{user_text}\n\n"
        f"你现在是「{display_name}」。历史里其他同伴的发言与自我介绍与你无关，"
        f"不要照抄他们的名字或人设。\n"
        f"每一句都要像「{display_name}」本人在说话，贴合系统里的人设与说话习惯；"
        "不要变成万能客服或干巴巴的播报员。\n"
        "一次只说该说的，别堆砌。\n"
        "【自我介绍】若对方说「介绍自己 / 你是谁 / 你能干嘛」之类：\n"
        f"- text 必须先自报「{display_name}」，再用角色口吻补一句你在这儿帮对方做什么；\n"
        "- 禁止反问爱好、职业、平时做什么；禁止只寒暄不介绍；\n"
        "- 一两句即可，别念职务说明书，也别复述 system 里的示例句原文。\n"
        f"- 若「之前的对话」里你（{display_name}）已经自我介绍过，"
        "后续轮次不要再重复报名字和职责，除非对方再次明确要求介绍。\n"
        "【表达】需要列多项时优先 Markdown 无序列表；也可用加粗/表格/代码块；"
        "保持简洁，别为了排版灌水。\n"
        "先在 thinking 写 1～4 句：对方真正在问什么（尤其别把「请你介绍」误判成「对方在介绍」）、"
        "该直接答还是追问、要不要转交同伴；thinking 只给学习者折叠查看，不要复述进 text。\n"
        "如果你判断这一棒该交给同伴（比如该考官出场、该让海绵宝宝整理 claim、"
        "该让派大星听你回讲），就在 handoff_to 填它的内部 agent_name "
        "(axiom/compass/echo/sage/critic)，并在 reason 写一句为什么转交；"
        "不需要转交就把 handoff_to / reason 设为 null。不要自己 @ 自己。"
        "对学习者说话时只用中文昵称，不要说 agent_name。\n"
        f"{plan_format}"
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
    today_plan_brief: str | None = None,
    plan_markdown_list: str | None = None,
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
        today_plan_brief=today_plan_brief,
        plan_markdown_list=plan_markdown_list,
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
    if (
        plan_markdown_list
        and is_plan_ask(user_text)
        and turn.text.strip()
    ):
        turn = turn.model_copy(
            update={
                "text": enforce_plan_reply(
                    turn.text,
                    plan_markdown_list,
                    display_name=ctx.identity.display_name,
                )
            }
        )
    return turn
