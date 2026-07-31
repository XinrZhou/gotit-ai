"""Deterministic interview countdown ramp tiers (framework-free; no LLM).

``hours_until = (scheduled_at - now).total_seconds() / 3600``

| tier    | condition        | push via ramp-nudges      |
|---------|------------------|---------------------------|
| past    | ``< 0``          | no                        |
| urgent  | ``≤ 24h``        | no (use D-1 / T-2h only)  |
| warm    | ``≤ 72h``        | yes (light project nudge) |
| light   | ``≤ 168h``       | yes (gentle mention)      |
| silent  | ``> 168h``       | no                        |
"""

from __future__ import annotations

from typing import Literal

InterviewRampTier = Literal["past", "urgent", "warm", "light", "silent"]

URGENT_HOURS = 24.0
WARM_HOURS = 72.0
LIGHT_HOURS = 168.0  # 7 days
RAMP_NUDGE_COOLDOWN_HOURS = 36.0

# Tiers that may produce a deliverable ramp nudge (not urgent — offsets handle that).
DELIVERABLE_TIERS: frozenset[InterviewRampTier] = frozenset({"light", "warm"})

_ROUND_HINT: dict[str, str] = {
    "tech_1": "技术一面",
    "tech_2": "技术二面",
    "tech_3": "技术三面",
    "tech_4": "技术四面",
    "hr": "HR 面",
}

_TIER_HINT_ZH: dict[InterviewRampTier, str] = {
    "past": "已过期",
    "urgent": "24 小时内",
    "warm": "临近 · 建议深挖",
    "light": "一周内 · 可练一练",
    "silent": "",
}


def ramp_tier(hours_until: float) -> InterviewRampTier:
    """Map hours until interview → ramp tier (pure, pinned by tests)."""
    if hours_until < 0:
        return "past"
    if hours_until <= URGENT_HOURS:
        return "urgent"
    if hours_until <= WARM_HOURS:
        return "warm"
    if hours_until <= LIGHT_HOURS:
        return "light"
    return "silent"


def tier_hint_zh(tier: InterviewRampTier) -> str:
    return _TIER_HINT_ZH.get(tier, "")


def suggest_action(*, round: str | None, project_name: str | None) -> str:
    """Short Chinese drill suggestion — no hype."""
    round_label = _ROUND_HINT.get((round or "").strip(), "")
    if not round_label and round:
        round_label = str(round).strip()
    focus = (project_name or "").strip() or "简历项目"
    if round_label:
        return f"{round_label}临近，可在「项目深挖」练练 {focus}"
    return f"面试临近，可在「项目深挖」练练 {focus}"


def hours_until(*, scheduled_at_ts: float, now_ts: float) -> float:
    """Seconds-based helper for tests / callers with unix timestamps."""
    return (scheduled_at_ts - now_ts) / 3600.0
