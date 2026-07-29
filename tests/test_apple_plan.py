"""Apple plan bridge: Notes parse + skip-merge (no osascript)."""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

_PARSE_PATH = (
    Path(__file__).resolve().parents[1] / "skills" / "apple-plan" / "parse.py"
)


def _load_parse():
    spec = importlib.util.spec_from_file_location("apple_plan_parse", _PARSE_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["apple_plan_parse"] = mod
    spec.loader.exec_module(mod)
    return mod


parse = _load_parse()


def test_parse_notes_happy_path() -> None:
    body = """
## 2026-07-30
- [ ] Review Redis TTL
- Read chapter 3

## 2026-07-31
* teach-back CAP
"""
    drafts = parse.parse_notes_body(body, note_title="学习计划")
    assert [(d.day.isoformat(), d.title) for d in drafts] == [
        ("2026-07-30", "Review Redis TTL"),
        ("2026-07-30", "Read chapter 3"),
        ("2026-07-31", "teach-back CAP"),
    ]


def test_parse_notes_rejects_prefix_noise() -> None:
    body = "杂记一下\n## 2026-07-30\n- ok\n"
    with pytest.raises(parse.NotesParseError, match="日期标题之前"):
        parse.parse_notes_body(body)


def test_parse_notes_rejects_bad_line() -> None:
    body = "## 2026-07-30\nnot a list item\n- ok\n"
    with pytest.raises(parse.NotesParseError, match="无法解析"):
        parse.parse_notes_body(body)


def test_parse_notes_requires_day_heading() -> None:
    with pytest.raises(parse.NotesParseError, match="未找到日期标题"):
        parse.parse_notes_body("- only a bullet")


def test_parse_notes_empty_day_block() -> None:
    with pytest.raises(parse.NotesParseError, match="没有清单"):
        parse.parse_notes_body("## 2026-07-30\n\n## 2026-07-31\n- x\n")


def test_parse_notes_strips_html() -> None:
    body = "<div><h2>2026-07-30</h2><ul><li>HTML item</li></ul></div>"
    # After strip, h2 becomes text line "2026-07-30" without ## — should fail OR
    # we need ## in body. Notes often export HTML with <div><b>…</b></div>.
    # Agreed format is markdown-ish; HTML list alone without ## date → error.
    with pytest.raises(parse.NotesParseError):
        parse.parse_notes_body(body)

    body2 = "## 2026-07-30<br>- HTML item\n"
    drafts = parse.parse_notes_body(body2)
    assert drafts[0].title == "HTML item"


def test_parse_time_hint_chinese_evening() -> None:
    assert parse.parse_time_hint("晚上7点 刷动态规划") == "19:00"
    assert parse.parse_time_hint("下午3点半复习") == "15:30"
    assert parse.parse_time_hint("早上8点起床学") == "08:00"
    assert parse.parse_time_hint("07:30 算法") == "07:30"
    assert parse.parse_time_hint("没有时间") == "09:00"


def test_reminders_to_drafts_maps_due() -> None:
    drafts, warnings = parse.reminders_to_drafts(
        [
            {"title": "A", "due": "2026-07-30", "id": "1"},
            {"title": "B", "due": None, "id": "2"},
            {"title": "C", "due": "2026-08-01T09:00:00", "id": "3"},
        ],
        date_from=date(2026, 7, 29),
        date_to=date(2026, 7, 31),
    )
    assert [d.title for d in drafts] == ["A"]
    assert any("无到期日" in w for w in warnings)
    assert "C" not in [d.title for d in drafts]


def test_reminders_all_undated_warns() -> None:
    drafts, warnings = parse.reminders_to_drafts(
        [{"title": "X", "due": None}, {"title": "Y", "due": None}]
    )
    assert drafts == []
    assert any("无任何可导入" in w for w in warnings)


def test_merge_skip_same_title() -> None:
    drafts = [
        parse.PlanDraft(day=date(2026, 7, 30), title="Redis"),
        parse.PlanDraft(day=date(2026, 7, 30), title="redis"),  # batch dup
        parse.PlanDraft(day=date(2026, 7, 30), title="New topic"),
        parse.PlanDraft(day=date(2026, 7, 31), title="Redis"),  # other day ok
    ]
    existing = {date(2026, 7, 30): {"redis"}}
    rows = parse.merge_with_existing(drafts, existing)
    actions = [(r.title, r.action) for r in rows]
    assert actions == [
        ("Redis", "skip"),
        ("redis", "skip"),
        ("New topic", "create"),
        ("Redis", "create"),
    ]
    stats = parse.summarize_merge(rows)
    assert stats == {"total": 4, "create": 2, "skip": 2}
