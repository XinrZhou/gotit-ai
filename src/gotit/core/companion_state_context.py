"""Compact learner-state brief for chat companion context (read-only).

Formats Ability Projection + next_action into a budgeted markdown block.
Chat must **not** treat this as write authority — mastery still closes only via
Verification Loop (``write_mastery_outcome``).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from gotit.core.ability_projection import AbilityStateProjection, AbilityStateView
from gotit.core.next_action import NextAction

# Hard caps — keep chat context small (no full history / full claim dump).
_MAX_MASTERED = 3
_MAX_WEAK = 3
_MAX_PENDING_LINES = 3
_EXCERPT = 48


def derive_growth_goal(
    *,
    next_act: NextAction | None,
    declining_ability: str | None = None,
    interview_lane: str | None = None,
    bootcamp_lane: str | None = None,
) -> str:
    """One-line growth focus for the companion (derived, not a new SoT)."""
    if next_act is not None and next_act.reason_code == "interview_drill":
        return "面试临近：项目深挖预习（练习场，不过门）"
    if interview_lane:
        return f"面试节奏：{interview_lane}"
    if bootcamp_lane and bootcamp_lane not in {"none", "done", "skipped"}:
        return "首通引导：走完出题→过门"
    if declining_ability:
        return f"稳住薄弱能力：{declining_ability}"
    if next_act is not None:
        return next_act.reason_text
    return "保持验证闭环：欠清或收工"


def _mastered_lines(abilities: list[AbilityStateView], *, limit: int) -> list[str]:
    rows = [a for a in abilities if a.mastered_count > 0]
    rows.sort(key=lambda a: (-a.mastered_count, a.ability))
    out: list[str] = []
    for a in rows[:limit]:
        out.append(f"- {a.ability}：已掌握 {a.mastered_count}/{a.claim_count}")
    return out or ["- （暂无已掌握 topic）"]


def _weak_lines(abilities: list[AbilityStateView], *, limit: int) -> list[str]:
    rows = [
        a
        for a in abilities
        if a.pending_review > 0
        or a.trajectory_failures > 0
        or a.recent_trend == "declining"
        or (a.claim_count > a.mastered_count)
    ]
    rows.sort(
        key=lambda a: (
            0 if a.recent_trend == "declining" else 1,
            -a.pending_review,
            -a.trajectory_failures,
            a.ability,
        )
    )
    out: list[str] = []
    for a in rows[:limit]:
        trend = a.recent_trend if a.recent_trend != "unknown" else "—"
        out.append(
            f"- {a.ability}：待复习 {a.pending_review}，趋势 {trend}，"
            f"弱点数 {len(a.weak_points)}"
        )
    return out or ["- （暂无明显薄弱 topic）"]


def _pending_lines(
    *,
    next_act: NextAction | None,
    abilities: list[AbilityStateView],
    limit: int,
) -> list[str]:
    lines: list[str] = []
    if next_act is not None and next_act.claim_id is not None:
        bit = next_act.ability or "claim"
        excerpt = ""
        for a in abilities:
            for w in a.weak_points:
                if w.claim_id == next_act.claim_id:
                    excerpt = (w.excerpt or "")[:_EXCERPT]
                    break
            if excerpt:
                break
        label = excerpt or str(next_act.claim_id)[:8]
        lines.append(
            f"- [{next_act.action}] {bit} · {label}"
            + (f"（{next_act.cta_label}）" if next_act.cta_label else "")
        )
    for a in abilities:
        if len(lines) >= limit:
            break
        for w in a.weak_points:
            if len(lines) >= limit:
                break
            if next_act and next_act.claim_id == w.claim_id:
                continue
            if w.status == "mastered":
                continue
            lines.append(
                f"- {a.ability} · {(w.excerpt or str(w.claim_id)[:8])[:_EXCERPT]}"
                f"（{w.status}）"
            )
    return lines or ["- （暂无待验证条目）"]


def format_companion_state_brief(
    *,
    as_of: date,
    ability: AbilityStateProjection,
    next_act: NextAction | None,
    growth_goal: str | None = None,
    interview_lane: str | None = None,
    bootcamp_lane: str | None = None,
) -> str:
    """Budgeted markdown for chat prompt injection (read-only)."""
    declining = next(
        (a.ability for a in ability.abilities if a.recent_trend == "declining"),
        None,
    )
    goal = growth_goal or derive_growth_goal(
        next_act=next_act,
        declining_ability=declining,
        interview_lane=interview_lane,
        bootcamp_lane=bootcamp_lane,
    )
    mastered = _mastered_lines(ability.abilities, limit=_MAX_MASTERED)
    weak = _weak_lines(ability.abilities, limit=_MAX_WEAK)
    pending = _pending_lines(
        next_act=next_act, abilities=ability.abilities, limit=_MAX_PENDING_LINES
    )
    if next_act is None:
        next_line = "- 下一步：空闲（可添加资料或收工）"
    else:
        next_line = (
            f"- 下一步：{next_act.action}（{next_act.reason_code}）"
            f" — {next_act.reason_text}"
        )

    return (
        f"截至 {as_of.isoformat()}（只读投影，非掌握写口）\n"
        f"### 成长目标\n- {goal}\n"
        f"### 下一步（状态驱动）\n{next_line}\n"
        "### 已掌握能力\n" + "\n".join(mastered) + "\n"
        "### 薄弱能力\n" + "\n".join(weak) + "\n"
        "### 待验证任务\n" + "\n".join(pending)
    )


def companion_state_guardrail() -> str:
    """Hard rule block appended near state brief in the chat prompt."""
    return (
        "【成长状态 · 硬规则】上文「学习者成长状态」是只读摘要：\n"
        "- 可据此调整语气、建议开练形式、提醒欠账；禁止假装已经改写了掌握档。\n"
        "- 掌握/排程只能经开考或回讲的 Verification Loop（Critic+gate）更新；"
        "聊天与工具 prepare 不能伪造「会了」。\n"
        "- 深挖/drill 是练习场，不过门，不算掌握。\n"
        "- 需要细节时用 get_ability_state / get_next_action / list_due_claims，"
        "不要编造 claim 或欠账条数。"
    )


def brief_to_debug_dict(brief: str) -> dict[str, Any]:
    return {"chars": len(brief), "lines": brief.count("\n") + 1}


__all__ = [
    "brief_to_debug_dict",
    "companion_state_guardrail",
    "derive_growth_goal",
    "format_companion_state_brief",
]
