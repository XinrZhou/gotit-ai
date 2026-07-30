"""Unit checks for digest v2 formatting (no network)."""

from __future__ import annotations

import importlib.util
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _ROOT / "skills" / "digest" / "fetch_digest.py"


def _load_fd():
    spec = importlib.util.spec_from_file_location("fetch_digest", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_evening_wrap_plus_tomorrow() -> None:
    fd = _load_fd()
    now = datetime(2026, 7, 29, 21, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    today = date(2026, 7, 29)
    tomorrow = date(2026, 7, 30)
    today_plan = {
        "items": [
            {"title": "健身", "status": "verified", "due_time": "07:00"},
            {"title": "复习 attention", "status": "planned"},
        ]
    }
    tomorrow_plan = {
        "date": "2026-07-30",
        "items": [
            {"title": "刷 DP", "status": "planned", "due_time": "11:00"},
            {"title": "做过的题", "status": "verified"},
        ],
    }
    text, picks, has_today = fd.format_evening(
        today_plan,
        None,
        tomorrow_plan,
        None,
        today=today,
        tomorrow=tomorrow,
        now=now,
    )
    assert "Tom 晚报" in text
    assert "今日复盘" in text
    assert "✓ 07:00 健身" in text
    assert "○ 复习 attention" in text
    assert "明日计划（2026-07-30）" in text
    assert "11:00 刷 DP" in text
    assert "做过的题" not in text
    assert "今日待检" not in text
    assert "早报" not in text
    assert picks == ["刷 DP"]
    assert has_today is True


def test_evening_today_only_empty_tomorrow() -> None:
    fd = _load_fd()
    now = datetime(2026, 7, 30, 21, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    text, picks, has_today = fd.format_evening(
        {"items": [{"title": "早上7点 健身", "status": "planned", "due_time": "07:00"}]},
        None,
        {"items": []},
        None,
        today=date(2026, 7, 30),
        tomorrow=date(2026, 7, 31),
        now=now,
    )
    assert "今日复盘" in text
    assert "○ 07:00 早上7点 健身" in text
    assert "明日暂无计划" in text
    assert "新建明日计划" in text
    assert "今日待检" not in text
    assert picks == []
    assert has_today is True


def test_evening_both_empty() -> None:
    fd = _load_fd()
    now = datetime(2026, 7, 29, 21, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    text, picks, has_today = fd.format_evening(
        {"items": []},
        None,
        {"items": []},
        None,
        today=date(2026, 7, 29),
        tomorrow=date(2026, 7, 30),
        now=now,
    )
    assert "今日无计划" in text
    assert "明日暂无计划" in text
    assert "①" in text and "②" in text
    assert "提醒事项" in text
    assert "备忘录" not in text
    assert picks == []
    assert has_today is False


def test_evening_has_no_due_or_news_mix() -> None:
    fd = _load_fd()
    now = datetime(2026, 7, 29, 21, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    text, picks, _ = fd.format_evening(
        {"items": []},
        None,
        {
            "items": [
                {"title": "复习 attention", "status": "planned"},
                {"title": "做过的题", "status": "verified"},
            ]
        },
        None,
        today=date(2026, 7, 29),
        tomorrow=date(2026, 7, 30),
        now=now,
    )
    assert "复习 attention" in text
    assert "做过的题" not in text
    assert "今日待检" not in text
    assert picks == ["复习 attention"]


def test_morning_is_plan_not_zaobao() -> None:
    fd = _load_fd()
    now = datetime(2026, 7, 30, 8, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    plan = {
        "items": [
            {"title": "刷动态规划", "status": "planned"},
            {"title": "健身", "status": "planned"},
        ]
    }
    text, picks = fd.format_morning_plan(plan, None, now=now)
    assert "今日计划" in text
    assert "早报" not in text
    assert "刷动态规划" in text
    assert "提醒事项" in text
    assert picks == ["刷动态规划", "健身"]


def test_morning_empty_plan_copy() -> None:
    fd = _load_fd()
    now = datetime(2026, 7, 29, 8, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    text, picks = fd.format_morning_plan({"items": []}, None, now=now)
    assert "今日暂无计划" in text
    assert "早报" not in text
    assert "提醒事项" in text
    assert "导入计划" in text
    assert "新建计划" in text
    assert "备忘录" not in text
    assert "\u3000" in text
    assert picks == []


def test_morning_marks_first_as_priority() -> None:
    fd = _load_fd()
    now = datetime(2026, 7, 30, 8, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    plan = {
        "date": "2026-07-30",
        "items": [
            {"title": "先做这条", "status": "planned"},
            {"title": "其次", "status": "planned"},
        ],
    }
    text, picks = fd.format_morning_plan(plan, None, now=now)
    assert "⭐ 优先：先做这条" in text
    assert "其次" in text
    assert picks[0] == "先做这条"


def test_open_titles_skips_done() -> None:
    fd = _load_fd()
    picks = fd._open_titles(
        {
            "items": [
                {"title": "A", "status": "planned"},
                {"title": "B", "status": "verified"},
                {"title": "A", "status": "planned"},
            ]
        }
    )
    assert picks == ["A"]
