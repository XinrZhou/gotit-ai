"""Companion state brief — budgeted read-only chat context."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from gotit.core.ability_projection import (
    AbilityClaimInput,
    AbilityTrajectoryInput,
    assemble_ability_state,
)
from gotit.core.agents.runtime import build_chat_prompt
from gotit.core.companion_state_context import (
    companion_state_guardrail,
    derive_growth_goal,
    format_companion_state_brief,
)
from gotit.core.next_action import NextAction


def _sample_ability():
    mastered_id = uuid4()
    weak_id = uuid4()
    return (
        assemble_ability_state(
            as_of=date(2026, 8, 4),
            user_id="u",
            claims=[
                AbilityClaimInput(
                    id=mastered_id,
                    text="Redis persistence RDB",
                    topic="redis",
                    status="mastered",
                ),
                AbilityClaimInput(
                    id=weak_id,
                    text="Kafka consumer lag tuning tip",
                    topic="kafka",
                    status="in_progress",
                    next_review_at=date(2026, 8, 4),
                ),
            ],
            trajectory=[
                AbilityTrajectoryInput(
                    claim_id=mastered_id, topic="redis", gate_verdict="passed"
                ),
                AbilityTrajectoryInput(
                    claim_id=weak_id, topic="kafka", gate_verdict="owe_next"
                ),
            ],
        ),
        weak_id,
    )


def test_format_companion_state_brief_sections() -> None:
    ability, weak_id = _sample_ability()
    action = NextAction(
        action="review",
        reason_code="due_review",
        reason_text="今日欠练，安排复习过门",
        claim_id=weak_id,
        ability="kafka",
        workflow="examine",
        open_key="open_examine",
        cta_label="开考",
    )
    brief = format_companion_state_brief(
        as_of=date(2026, 8, 4),
        ability=ability,
        next_act=action,
    )
    assert "成长目标" in brief
    assert "已掌握能力" in brief
    assert "薄弱能力" in brief
    assert "待验证任务" in brief
    assert "下一步" in brief
    assert "redis" in brief
    assert "kafka" in brief
    assert "只读投影" in brief
    assert len(brief) < 2000


def test_derive_growth_goal_interview() -> None:
    action = NextAction(
        action="drill",
        reason_code="interview_drill",
        reason_text="面试临近",
        workflow="drill",
        open_key="open_drill",
        cta_label="练深挖",
    )
    assert "面试" in derive_growth_goal(next_act=action)


def test_build_chat_prompt_injects_state_and_guardrail() -> None:
    ability, _ = _sample_ability()
    brief = format_companion_state_brief(
        as_of=date(2026, 8, 4),
        ability=ability,
        next_act=None,
        interview_lane="warm",
    )
    prompt = build_chat_prompt(
        user_text="我接下来该练什么",
        history=[],
        memory=[],
        display_name="章鱼哥",
        learner_state_brief=brief,
    )
    assert "## 学习者成长状态" in prompt
    assert "【成长状态 · 硬规则】" in prompt
    assert companion_state_guardrail().split("\n", 1)[0] in prompt
    assert "禁止假装" in prompt
    assert "Verification Loop" in prompt
