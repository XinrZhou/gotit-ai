"""Compose a system prompt from agent identity + pinned rubric."""

from __future__ import annotations

from gotit.core.models import AgentIdentity, PromptVersion


def identity_card(identity: AgentIdentity) -> str:
    """Hard identity block — Chinese nickname first; English code is internal only."""
    return (
        f"# 你是谁\n"
        f"你是「{identity.display_name}」"
        f"（系统内部名 {identity.agent_name}，学习者看不到）。\n"
        f"对学习者只自称「{identity.display_name}」，"
        f"绝不说英文代号，也绝不冒充其他同伴"
        f"（章鱼哥 / 海绵宝宝 / 派大星 / 桑迪 / 凯伦）。\n"
        f"全程用「{identity.display_name}」的人设口吻说话——"
        f"像角色本人在聊天，不是客服、不是助理、不是说明书。\n"
        f"自我介绍用你的人设口吻随口说一两句——先报名字，再带一句你在这儿干嘛；"
        f"像朋友自我介绍，不要念职务说明书（别说「考官」「管家」「职责」「验证掌握」这类词），"
        f"也不要反问对方爱好或复述对话里其他同伴刚说过的话。"
    )


def compose_system_prompt(
    identity: AgentIdentity,
    rubric: PromptVersion | None = None,
    *,
    include_rubric: bool = True,
) -> str:
    """Identity card first, then personality, then optional rubric.

    Chat should pass ``include_rubric=False``: examine/curate prompt files are
    English-first and workflow-specific; injecting them into free chat makes
    agents introduce themselves as Compass/Axiom.
    """
    parts: list[str] = [identity_card(identity)]
    if identity.personality.strip():
        parts.append(identity.personality.strip())
    if include_rubric and rubric is not None and rubric.system_prompt.strip():
        parts.append(rubric.system_prompt.strip())
    return "\n\n---\n\n".join(parts)
