"""Chat prompt injects today's plan brief."""

from datetime import date
from uuid import uuid4

from gotit.core.agents.runtime import (
    build_chat_prompt,
    enforce_plan_reply,
    format_plan_markdown_list,
    format_today_plan_brief,
    is_plan_ask,
)
from gotit.core.models import DayPlanView, PlanItemSource, PlanItemStatus, PlanItemView


def _item(title: str, *, status: PlanItemStatus, due_time: str | None = None) -> PlanItemView:
    return PlanItemView(
        id=uuid4(),
        title=title,
        source=PlanItemSource.MANUAL,
        status=status,
        due_time=due_time,
    )


def test_format_today_plan_brief_empty() -> None:
    brief = format_today_plan_brief(None, day_label="2026-07-30")
    assert "2026-07-30" in brief
    assert "还没有计划条目" in brief


def test_format_today_plan_brief_orders_by_time() -> None:
    plan = DayPlanView(
        date=date(2026, 7, 30),
        user_id="local",
        items=[
            _item("晚上刷题", status=PlanItemStatus.PLANNED, due_time="19:00"),
            _item("早上健身", status=PlanItemStatus.PLANNED, due_time="07:00"),
            _item("已过关的题", status=PlanItemStatus.VERIFIED, due_time="08:00"),
        ],
    )
    brief = format_today_plan_brief(plan)
    assert brief.index("07:00") < brief.index("19:00")
    assert brief.index("健身") < brief.index("已过关的题")


def test_format_today_plan_brief_can_omit_list() -> None:
    plan = DayPlanView(
        date=date(2026, 7, 30),
        user_id="local",
        items=[_item("健身", status=PlanItemStatus.PLANNED, due_time="07:00")],
    )
    brief = format_today_plan_brief(plan, include_list=False)
    assert "共 1 条" in brief
    assert "07:00" not in brief
    assert "健身" not in brief


def test_clean_title_drops_time_when_due_time_set() -> None:
    plan = DayPlanView(
        date=date(2026, 7, 30),
        user_id="local",
        items=[
            _item("早上7点健身", status=PlanItemStatus.PLANNED, due_time="07:00"),
            _item("晚上7点刷动态规划", status=PlanItemStatus.PLANNED, due_time="19:00"),
        ],
    )
    md = format_plan_markdown_list(plan)
    assert md is not None
    assert "- 07:00 健身（待做）" in md
    assert "- 19:00 刷动态规划（待做）" in md
    assert "早上7点" not in md


def test_clean_title_drops_period_word_when_due_time_set() -> None:
    plan = DayPlanView(
        date=date(2026, 7, 30),
        user_id="local",
        items=[_item("早上健身", status=PlanItemStatus.PLANNED, due_time="07:00")],
    )
    md = format_plan_markdown_list(plan)
    assert md is not None
    assert "- 07:00 健身（待做）" in md
    assert "早上" not in md


def test_is_plan_ask() -> None:
    assert is_plan_ask("说下我今天的计划")
    assert is_plan_ask("今日安排是啥")
    assert not is_plan_ask("介绍下你自己")


def test_enforce_plan_reply_strips_paraphrase() -> None:
    skeleton = "- 07:00 健身（待做）\n- 19:00 刷动态规划（待做）"
    bad = (
        "嗨呀！早上7点记得去健身哦，晚上7点要刷动态规划呢！\n\n"
        f"{skeleton}"
    )
    out = enforce_plan_reply(bad, skeleton, display_name="海绵宝宝")
    assert out == f"今天排好啦——\n\n{skeleton}"
    assert "记得" not in out
    assert out.count("健身") == 1


def test_enforce_plan_reply_keeps_safe_opener() -> None:
    skeleton = "- 07:00 健身（待做）"
    good = f"排好啦～\n\n{skeleton}"
    out = enforce_plan_reply(good, skeleton, display_name="海绵宝宝")
    assert out.startswith("排好啦～\n\n")
    assert skeleton in out


def test_build_chat_prompt_includes_plan_and_guardrail() -> None:
    plan = DayPlanView(
        date=date(2026, 7, 30),
        user_id="local",
        items=[
            _item("晚上刷题", status=PlanItemStatus.PLANNED, due_time="19:00"),
            _item("早上健身", status=PlanItemStatus.PLANNED, due_time="07:00"),
        ],
    )
    skeleton = format_plan_markdown_list(plan)
    brief = format_today_plan_brief(plan, include_list=False)
    prompt = build_chat_prompt(
        user_text="说下我今天的计划",
        history=[],
        memory=[],
        display_name="海绵宝宝",
        today_plan_brief=brief,
        plan_markdown_list=skeleton,
    )
    assert "## 今日计划" in prompt
    assert "【今日计划 · 硬规则】" in prompt
    assert "列表骨架" in prompt
    assert skeleton is not None
    assert "- 07:00 健身（待做）" in prompt
    assert "反例" in prompt
    assert "正例" in prompt
    # Brief must not duplicate the bullet list (avoids paraphrase).
    plan_section = prompt.split("## 今日计划", 1)[1].split("## 之前的对话", 1)[0]
    assert "- 07:00" not in plan_section
