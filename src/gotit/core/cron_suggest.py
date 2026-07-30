"""Natural-language → 5-field cron (minute hour day month weekday).

Framework-free heuristics for common Chinese / English wall-clock phrases.
LLM fallback lives in the API route.
"""

from __future__ import annotations

import re

_CRON_RE = re.compile(
    r"^(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)$"
)


def normalize_cron(expr: str) -> str | None:
    text = " ".join((expr or "").strip().split())
    if not text or not _CRON_RE.fullmatch(text):
        return None
    return text


def suggest_cron_from_text(text: str) -> str | None:
    """Best-effort parse. Returns None if not confident."""
    raw = (text or "").strip()
    if not raw:
        return None
    direct = normalize_cron(raw)
    if direct:
        return direct

    lower = raw.lower()

    # HH:MM or H:MM (optional 每天/每日)
    m = re.search(r"(?:每天|每日|每天的|every\s+day)?\s*([01]?\d|2[0-3])\s*[:：]\s*([0-5]\d)", raw)
    if m:
        return f"{int(m.group(2))} {int(m.group(1))} * * *"

    # 早上/上午/中午/下午/晚上 + N点(半)?
    m = re.search(
        r"(凌晨|早上|上午|中午|下午|晚上|傍晚|今晚)?"
        r"\s*([0-2]?\d)\s*(?:点|时|:|：)\s*(半|[0-5]?\d)?",
        raw,
    )
    if m:
        period = m.group(1) or ""
        hour = int(m.group(2))
        minute_raw = m.group(3)
        if minute_raw == "半":
            minute = 30
        elif minute_raw and minute_raw.isdigit():
            minute = int(minute_raw)
        else:
            minute = 0
        if hour > 23:
            return None
        if period in {"下午", "晚上", "傍晚", "今晚"} and 1 <= hour <= 11:
            hour += 12
        elif period == "中午" and hour < 11:
            hour = 12 if hour == 0 else hour
        elif hour == 12 and period in {"凌晨", "早上", "上午"}:
            hour = 0
        if hour > 23:
            return None
        return f"{minute} {hour} * * *"

    # "8am" / "9 pm"
    m = re.search(r"\b([01]?\d|2[0-3])\s*(am|pm)\b", lower)
    if m:
        hour = int(m.group(1))
        if m.group(2) == "pm" and hour < 12:
            hour += 12
        if m.group(2) == "am" and hour == 12:
            hour = 0
        return f"0 {hour} * * *"

    # bare "每天9点" already covered; try "九点" cn numerals lightly
    cn = {
        "零": 0,
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
    }
    m = re.search(
        r"(凌晨|早上|上午|中午|下午|晚上|傍晚)?"
        r"\s*([零一二两三四五六七八九十]+)\s*点\s*(半)?",
        raw,
    )
    if m:
        period = m.group(1) or ""
        token = m.group(2)
        minute = 30 if m.group(3) else 0
        if token == "十":
            hour = 10
        elif token.startswith("十"):
            hour = 10 + cn.get(token[1:], 0)
        elif token.endswith("十") and len(token) == 2:
            hour = cn.get(token[0], 0) * 10
        else:
            parsed = cn.get(token)
            if parsed is None:
                return None
            hour = parsed
        if period in {"下午", "晚上", "傍晚"} and 1 <= hour <= 11:
            hour += 12
        elif period == "中午" and hour < 11:
            hour = 12 if hour == 0 else hour
        return f"{minute} {hour} * * *"

    return None
