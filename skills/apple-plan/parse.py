"""Pure parsing + merge helpers for Apple → gotit plan import.

No AppleScript / EventKit / network here — safe for pytest.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

DAY_HEADING_RE = re.compile(
    r"^#{1,3}\s*(\d{4}-\d{2}-\d{2})\s*$",
    re.MULTILINE,
)
LIST_ITEM_RE = re.compile(
    r"^[\-\*]\s+(?:\[[ xX]\]\s+)?(.+?)\s*$",
)
HTML_TAG_RE = re.compile(r"(?is)<[^>]+>")
BLANK_RE = re.compile(r"^\s*$")


class NotesParseError(ValueError):
    """Notes body does not match the agreed study-plan format."""


@dataclass(frozen=True, slots=True)
class PlanDraft:
    day: date
    title: str
    origin: str = ""  # e.g. reminder id / note title


Action = Literal["create", "skip"]


@dataclass(frozen=True, slots=True)
class MergeRow:
    day: date
    title: str
    action: Action
    origin: str = ""
    reason: str = ""


def _strip_html(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = HTML_TAG_RE.sub("\n", text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\r\n?", "\n", text)
    return text


def parse_notes_body(body: str, *, note_title: str = "") -> list[PlanDraft]:
    """Parse Notes body into day/title drafts.

    Expected format::

        ## 2026-07-30
        - [ ] Review Redis
        - Read chapter 3

        ## 2026-07-31
        - teach-back CAP

    Raises NotesParseError on any structural failure (no silent drop).
    """
    raw = _strip_html(body).strip()
    if not raw:
        raise NotesParseError("笔记正文为空，无法导入学习计划")

    matches = list(DAY_HEADING_RE.finditer(raw))
    if not matches:
        raise NotesParseError(
            "未找到日期标题（需要形如 `## YYYY-MM-DD`）。"
            "请按约定格式整理备忘录后再导入。"
        )

    prefix = raw[: matches[0].start()]
    if prefix.strip():
        raise NotesParseError(
            f"日期标题之前有无法识别的内容（已拒绝静默丢弃）：{prefix.strip()[:80]!r}"
        )

    drafts: list[PlanDraft] = []
    origin = note_title or "notes"

    for i, m in enumerate(matches):
        day_s = m.group(1)
        try:
            day = date.fromisoformat(day_s)
        except ValueError as exc:
            raise NotesParseError(f"非法日期标题：{day_s}") from exc

        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        section = raw[start:end]
        titles = _parse_section_lines(section, day=day_s)
        if not titles:
            raise NotesParseError(f"日期 {day_s} 下没有清单条目（需要 `-` / `- [ ]` 行）")
        for title in titles:
            drafts.append(PlanDraft(day=day, title=title, origin=origin))

    return drafts


def _parse_section_lines(section: str, *, day: str) -> list[str]:
    titles: list[str] = []
    for lineno, line in enumerate(section.splitlines(), start=1):
        if BLANK_RE.match(line):
            continue
        # Nested headings inside a day block are not allowed.
        if re.match(r"^#{1,6}\s+", line):
            raise NotesParseError(
                f"日期 {day} 区块内出现额外标题（第 {lineno} 行）：{line.strip()!r}"
            )
        m = LIST_ITEM_RE.match(line)
        if not m:
            raise NotesParseError(
                f"日期 {day} 区块内有无法解析的行（第 {lineno} 行，拒绝静默丢弃）："
                f"{line.strip()!r}"
            )
        title = m.group(1).strip()
        if not title:
            raise NotesParseError(f"日期 {day} 区块内有空清单项（第 {lineno} 行）")
        titles.append(title)
    return titles


def reminders_to_drafts(
    items: list[dict],
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> tuple[list[PlanDraft], list[str]]:
    """Map Reminders JSON rows → drafts.

    Each item: ``{title, due, id?}`` where ``due`` is ISO date or datetime.
    Returns (drafts, warnings). Errors (empty list name etc.) belong to the caller.
    """
    drafts: list[PlanDraft] = []
    warnings: list[str] = []
    if not items:
        return drafts, warnings

    undated = 0
    for raw in items:
        title = str(raw.get("title") or "").strip()
        if not title:
            warnings.append("跳过无标题提醒")
            continue
        due_raw = raw.get("due")
        if not due_raw:
            undated += 1
            warnings.append(f"跳过无到期日的提醒：{title!r}")
            continue
        day = _parse_due(str(due_raw))
        if day is None:
            warnings.append(f"跳过到期日无法解析的提醒：{title!r} due={due_raw!r}")
            continue
        if date_from is not None and day < date_from:
            continue
        if date_to is not None and day > date_to:
            continue
        origin = str(raw.get("id") or "reminder")
        drafts.append(PlanDraft(day=day, title=title, origin=origin))

    if undated and not drafts:
        # Caller may treat "all undated" as hard failure.
        warnings.append(f"共 {undated} 条提醒缺少到期日，无任何可导入条目")
    return drafts, warnings


def _parse_due(value: str) -> date | None:
    value = value.strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        pass
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            normalized = value.replace("Z", "+0000")
            return datetime.strptime(normalized, fmt).date()
        except ValueError:
            continue
    return None


def parse_time_hint(title: str, *, default: str = "09:00") -> str:
    """Extract HH:MM from a Chinese/English title; else default.

    Examples: 「晚上7点 刷题」→ 19:00；「下午3点半」→ 15:30；「07:30 复习」→ 07:30
    """
    text = (title or "").strip()
    if not text:
        return default

    # Prefer explicit 24h clock first
    m24 = re.search(r"\b([01]?\d|2[0-3])[:：]([0-5]\d)\b", text)
    if m24:
        return f"{int(m24.group(1)):02d}:{int(m24.group(2)):02d}"

    m = re.search(
        r"(凌晨|早上|上午|中午|下午|晚上|傍晚|今晚|明早)?"
        r"\s*(\d{1,2})\s*(?:[:：点时])\s*(\d{1,2}|半)?",
        text,
    )
    if not m:
        return default

    period = m.group(1) or ""
    hour = int(m.group(2))
    minute_raw = m.group(3)
    if minute_raw == "半":
        minute = 30
    elif minute_raw:
        minute = int(minute_raw)
    else:
        minute = 0

    if hour > 23:
        return default
    if minute > 59:
        minute = 0

    # Apply Chinese period heuristics when hour is 1–12 style
    if period in {"下午", "晚上", "傍晚", "今晚"} and 1 <= hour <= 11:
        hour += 12
    elif period == "中午" and hour < 11:
        hour = 12 if hour == 0 else hour
    elif hour == 12 and period in {"凌晨", "早上", "上午", "明早"}:
        hour = 0
    # 「晚上7点」already handled; 「晚上12点」→ 0 next day — keep 0 for simplicity

    if hour > 23:
        return default
    return f"{hour:02d}:{minute:02d}"


def merge_with_existing(
    drafts: list[PlanDraft],
    existing_by_day: dict[date, set[str]],
) -> list[MergeRow]:
    """Same-day title casefold dedupe: existing → skip, else create."""
    rows: list[MergeRow] = []
    seen_in_batch: dict[date, set[str]] = {}
    for d in drafts:
        key = d.title.casefold()
        batch = seen_in_batch.setdefault(d.day, set())
        existing = existing_by_day.get(d.day, set())
        if key in existing or key in batch:
            rows.append(
                MergeRow(
                    day=d.day,
                    title=d.title,
                    action="skip",
                    origin=d.origin,
                    reason="同日已有同标题",
                )
            )
            continue
        batch.add(key)
        rows.append(
            MergeRow(day=d.day, title=d.title, action="create", origin=d.origin)
        )
    return rows


def summarize_merge(rows: list[MergeRow]) -> dict[str, int]:
    return {
        "total": len(rows),
        "create": sum(1 for r in rows if r.action == "create"),
        "skip": sum(1 for r in rows if r.action == "skip"),
    }
