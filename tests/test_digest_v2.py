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


def test_evening_has_no_due_or_news_mix() -> None:
    fd = _load_fd()
    now = datetime(2026, 7, 29, 21, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    tomorrow = date(2026, 7, 30)
    plan = {
        "date": "2026-07-30",
        "items": [
            {"title": "复习 attention", "status": "planned"},
            {"title": "做过的题", "status": "verified"},
        ],
    }
    text, picks = fd.format_evening_tomorrow(plan, None, tomorrow=tomorrow, now=now)
    assert "明日安排" in text
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


def test_evening_empty_cta_structure() -> None:
    fd = _load_fd()
    now = datetime(2026, 7, 29, 21, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    tomorrow = date(2026, 7, 30)
    text, picks = fd.format_evening_tomorrow(
        {"items": []}, None, tomorrow=tomorrow, now=now
    )
    assert "明日暂无计划" in text
    assert "①" in text and "②" in text
    assert "提醒事项" in text
    assert "新建明日计划" in text
    assert "备忘录" not in text
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
