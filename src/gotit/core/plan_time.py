"""Plan due_time helpers (HH:MM) — framework-free."""

from __future__ import annotations

import re

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def normalize_due_time(value: str | None) -> str | None:
    """Return HH:MM or None if empty/invalid."""
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    m = _TIME_RE.fullmatch(text)
    if not m:
        return None
    return f"{int(m.group(1)):02d}:{m.group(2)}"


def parse_time_hint(title: str, *, default: str | None = None) -> str | None:
    """Extract HH:MM from a Chinese/English title; else default (or None)."""
    text = (title or "").strip()
    if not text:
        return default

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

    if period in {"下午", "晚上", "傍晚", "今晚"} and 1 <= hour <= 11:
        hour += 12
    elif period == "中午" and hour < 11:
        hour = 12 if hour == 0 else hour
    elif hour == 12 and period in {"凌晨", "早上", "上午", "明早"}:
        hour = 0

    if hour > 23:
        return default
    return f"{hour:02d}:{minute:02d}"


def resolve_due_time(*, due_time: str | None, title: str) -> str | None:
    """Prefer explicit due_time; else parse title; else None."""
    explicit = normalize_due_time(due_time)
    if explicit:
        return explicit
    return parse_time_hint(title, default=None)
