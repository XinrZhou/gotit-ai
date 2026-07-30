#!/usr/bin/env python3
"""OpenClaw digest helper: plan touchpoints + optional AI/YouTube RSS.

Usage:
  python skills/digest/fetch_digest.py morning   # today's plan
  python skills/digest/fetch_digest.py evening   # tomorrow plan Q&A
  python skills/digest/fetch_digest.py news      # RSS only (never mixes plan)

Prefer: uv run --directory <gotit-ai> python skills/digest/fetch_digest.py evening
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

USER_AGENT = "GotitDigest/0.2 (+https://github.com/gotit-ai; OpenClaw skill)"
DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.json")
TIMEOUT_S = 12
OPEN_PLAN_STATUSES = {"planned", "in_progress", "deferred"}
DONE_PLAN_STATUSES = {"verified", "done", "passed", "cancelled", "canceled", "skipped", "failed"}


def _load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _strip_html(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _truncate(text: str, n: int = 80) -> str:
    text = _strip_html(text)
    if len(text) <= n:
        return text
    return text[: n - 1].rstrip() + "…"


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _child_text(el: ET.Element, *names: str) -> str:
    want = set(names)
    for child in el:
        if _local_name(child.tag) in want:
            return (child.text or "").strip() or "".join(child.itertext()).strip()
    return ""


def _parse_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value.replace("Z", "+0000"), fmt)
        except ValueError:
            continue
    return None


def _fetch_bytes(url: str) -> tuple[bytes | None, str | None]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            return resp.read(), None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _parse_feed(data: bytes, feed_id: str, label: str) -> list[dict]:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError(f"XML parse error: {exc}") from exc

    items: list[dict] = []
    for item in root.iter():
        if _local_name(item.tag) != "item":
            continue
        title = _child_text(item, "title")
        link = _child_text(item, "link")
        desc = _child_text(item, "description", "summary", "content")
        pub = _child_text(item, "pubDate", "published", "updated", "date")
        if not title:
            continue
        items.append(
            {
                "feed_id": feed_id,
                "label": label,
                "title": _strip_html(title),
                "link": link,
                "summary": _truncate(desc, 90),
                "published": _parse_date(pub),
            }
        )
    if items:
        return items

    for entry in root.iter():
        if _local_name(entry.tag) != "entry":
            continue
        title = _child_text(entry, "title")
        link = ""
        for child in entry:
            if _local_name(child.tag) == "link":
                href = child.attrib.get("href", "")
                rel = child.attrib.get("rel", "alternate")
                if href and rel in ("alternate", ""):
                    link = href
                    break
        if not link:
            link = _child_text(entry, "id")
        desc = _child_text(entry, "summary", "content")
        pub = _child_text(entry, "published", "updated")
        if not title:
            continue
        items.append(
            {
                "feed_id": feed_id,
                "label": label,
                "title": _strip_html(title),
                "link": link,
                "summary": _truncate(desc, 90),
                "published": _parse_date(pub),
            }
        )
    return items


def collect_items(cfg: dict) -> tuple[list[dict], list[str]]:
    errors: list[str] = []
    buckets: list[list[dict]] = []
    keywords = [k.strip().casefold() for k in (cfg.get("keywords") or []) if str(k).strip()]

    for feed in cfg.get("feeds") or []:
        if feed.get("enabled") is False:
            continue
        url = feed.get("url") or ""
        fid = feed.get("id") or url
        label = feed.get("label") or fid
        if not url:
            continue
        data, err = _fetch_bytes(url)
        if err or data is None:
            errors.append(f"{label}: {err or 'empty'}")
            continue
        try:
            parsed = _parse_feed(data, fid, label)
        except ValueError as exc:
            errors.append(f"{label}: {exc}")
            continue
        if not parsed:
            errors.append(f"{label}: no items")
            continue
        if keywords:
            parsed = [
                x
                for x in parsed
                if any(k in (x.get("title") or "").casefold() for k in keywords)
            ]
            if not parsed:
                errors.append(f"{label}: no keyword match")
                continue

        def _sort_key(x: dict) -> datetime:
            pub = x["published"]
            if pub is None:
                return datetime.min.replace(tzinfo=ZoneInfo("UTC"))
            if pub.tzinfo is None:
                return pub.replace(tzinfo=ZoneInfo("UTC"))
            return pub

        parsed.sort(key=_sort_key, reverse=True)
        buckets.append(parsed)

    picked: list[dict] = []
    seen_titles: set[str] = set()
    limit = int(cfg.get("item_count") or 3)
    idx = 0
    while len(picked) < limit and buckets:
        progressed = False
        for bucket in buckets:
            if idx >= len(bucket):
                continue
            item = bucket[idx]
            key = item["title"].casefold()
            if key in seen_titles:
                continue
            seen_titles.add(key)
            picked.append(item)
            progressed = True
            if len(picked) >= limit:
                break
        idx += 1
        if not progressed:
            break
    return picked, errors


def format_news(items: list[dict], errors: list[str], *, heading: str, now: datetime) -> str:
    lines = [heading, f"时间 {now.strftime('%Y-%m-%d %H:%M')}（Asia/Shanghai）", ""]
    if not items:
        lines.append("资讯抓取失败或无匹配条目。")
    else:
        for i, item in enumerate(items, 1):
            lines.append(f"{i}. 【{item['label']}】{item['title']}")
            if item.get("summary"):
                lines.append(f"   {item['summary']}")
            if item.get("link"):
                lines.append(f"   {item['link']}")
            lines.append("")
    if errors:
        lines.append("——")
        lines.append("部分源失败（已降级，未静默）：")
        for err in errors[:6]:
            lines.append(f"· {err}")
    return "\n".join(lines).rstrip() + "\n"


def _plan_via_rest(api_url: str, day: date) -> dict | None:
    import os

    base = api_url.rstrip("/")
    key = os.environ.get("GOTIT_API_KEY", "").strip()
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(
        f"{base}/v1/days/{day.isoformat()}/plan", headers=headers
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _plan_via_db(day: date) -> dict | None:
    import asyncio

    async def _run() -> dict:
        from gotit.db.ops import get_plan
        from gotit.db.runtime import ensure_db
        from gotit.db.session import session_scope

        await ensure_db()
        async with session_scope() as session:
            view = await get_plan(session, day)
        return view.model_dump(mode="json")

    return asyncio.run(_run())


def _prefs_via_db() -> dict | None:
    import asyncio

    async def _run() -> dict:
        from gotit.db.ops import get_digest_prefs
        from gotit.db.runtime import ensure_db
        from gotit.db.session import session_scope

        await ensure_db()
        async with session_scope() as session:
            prefs = await get_digest_prefs(session)
        return prefs.model_dump(mode="json")

    return asyncio.run(_run())


def _prefs_via_rest(api_url: str) -> dict | None:
    import os

    base = api_url.rstrip("/")
    key = os.environ.get("GOTIT_API_KEY", "").strip()
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(f"{base}/v1/shell/digest-prefs", headers=headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8"))


def merge_prefs(file_cfg: dict) -> dict:
    """Prefer gotit digest_prefs when reachable; else file config."""
    gotit = file_cfg.get("gotit") or {}
    api_url = (gotit.get("api_url") or "").strip()
    remote: dict | None = None
    try:
        remote = _prefs_via_rest(api_url) if api_url else _prefs_via_db()
    except Exception:  # noqa: BLE001
        remote = None
    if not remote:
        return dict(file_cfg)
    merged = dict(file_cfg)
    for key in (
        "timezone",
        "item_count",
        "morning_cron",
        "evening_cron",
        "news_cron",
        "news_enabled",
        "morning_include_news",
        "evening_include_news",
        "keywords",
        "feeds",
        "notes_open_url",
    ):
        if key in remote and remote[key] is not None:
            merged[key] = remote[key]
    return merged


def load_plan(cfg: dict, day: date) -> tuple[dict | None, str | None]:
    gotit = cfg.get("gotit") or {}
    api_url = (gotit.get("api_url") or "").strip()
    if api_url:
        try:
            return _plan_via_rest(api_url, day), None
        except Exception as exc:  # noqa: BLE001
            return None, f"REST plan 失败: {exc}"
    try:
        return _plan_via_db(day), None
    except Exception as exc:  # noqa: BLE001
        return None, f"db get_plan 失败: {exc}"


def _open_titles(plan: dict | None) -> list[str]:
    if not plan:
        return []
    picks: list[str] = []
    seen: set[str] = set()
    for it in plan.get("items") or []:
        status = (it.get("status") or "").lower()
        if status in DONE_PLAN_STATUSES:
            continue
        if status in {"verified", "failed"}:
            continue
        title = (it.get("title") or "").strip()
        key = title.casefold()
        if not title or key in seen:
            continue
        seen.add(key)
        picks.append(title)
    return picks


# WeChat collapses pure empty lines; keep a fullwidth-space line as spacer.
_WX_BLANK = "\u3000"


def format_morning_plan(
    plan: dict | None,
    err: str | None,
    *,
    now: datetime,
    notes_open_url: str | None = None,  # unused; kept for call-site compat
) -> tuple[str, list[str]]:
    del notes_open_url
    day_s = now.date().isoformat()
    lines = [
        "🐱 Tom · 今日计划",
        f"{day_s} · {now.strftime('%H:%M')}",
        _WX_BLANK,
    ]
    if err:
        lines.append(f"无法读取计划：{err}")
        return "\n".join(lines), []

    picks = _open_titles(plan)
    if not picks:
        lines.append("今日暂无计划。")
        lines.append(_WX_BLANK)
        lines.extend(_plan_cta(which="today"))
    else:
        lines.append(f"⭐ 优先：{_truncate(picks[0], 80)}")
        if len(picks) > 1:
            lines.append(_WX_BLANK)
            for i, text in enumerate(picks[1:6], 1):
                lines.append(f"{i}. {_truncate(text, 80)}")
        lines.append(_WX_BLANK)
        lines.append("已同步到提醒事项「学习计划」。做完走 gotit examine / 回讲。")
    return "\n".join(lines), picks


def _plan_cta(*, which: str) -> list[str]:
    """Empty-plan CTA — Reminders first; WeChat-friendly spacers."""
    if which == "today":
        invent = "新建计划：……"
    else:
        invent = "新建明日计划：……"
    return [
        "① 打开「提醒事项」写好后，回「导入计划」",
        "（列表「学习计划」；条目需带到期日）",
        _WX_BLANK,
        f"② 或直接说：{invent}",
        "（会写入 gotit，并同步到提醒事项）",
    ]


def format_evening_tomorrow(
    plan: dict | None,
    err: str | None,
    *,
    tomorrow: date,
    now: datetime,
    notes_open_url: str | None = None,  # unused; kept for call-site compat
) -> tuple[str, list[str]]:
    del notes_open_url
    lines = [
        "🐱 Tom 晚报 · 明日计划",
        f"{tomorrow.isoformat()} · {now.strftime('%H:%M')}",
        _WX_BLANK,
    ]
    if err:
        lines.append(f"无法读取明日计划：{err}")
        return "\n".join(lines), []

    picks = _open_titles(plan)
    if not picks:
        lines.append("明日暂无计划。")
        lines.append(_WX_BLANK)
        lines.extend(_plan_cta(which="tomorrow"))
    else:
        lines.append("明日安排：")
        lines.append(_WX_BLANK)
        for i, text in enumerate(picks[:8], 1):
            lines.append(f"{i}. {_truncate(text, 80)}")
        lines.append(_WX_BLANK)
        lines.append("改 →「调整…」　OK →「保持」")
        lines.append("已同步到提醒事项「学习计划」。")
    return "\n".join(lines), picks


def _items_payload(items: list[dict]) -> list[dict]:
    out: list[dict] = []
    for i, item in enumerate(items, 1):
        out.append(
            {
                "n": i,
                "title": item.get("title") or "",
                "link": item.get("link"),
                "feed_id": item.get("feed_id"),
                "label": item.get("label"),
            }
        )
    return out


def _writeback_rest(api_url: str, payload: dict) -> tuple[str | None, str | None]:
    import os

    base = api_url.rstrip("/")
    key = os.environ.get("GOTIT_API_KEY", "").strip()
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if key:
        headers["Authorization"] = f"Bearer {key}"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/v1/shell/events", data=body, headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return str(data.get("id") or ""), None


def _writeback_db(payload: dict) -> tuple[str | None, str | None]:
    import asyncio

    async def _run() -> str:
        from gotit.db.ops import record_shell_event
        from gotit.db.runtime import ensure_db
        from gotit.db.session import session_scope

        await ensure_db()
        async with session_scope() as session:
            entry = await record_shell_event(
                session,
                job=str(payload["job"]),
                items=list(payload.get("items") or []),
                due_summary=list(payload.get("due_summary") or []),
                errors=list(payload.get("errors") or []),
                delivery_ok=payload.get("delivery_ok"),
                channel=str(payload.get("channel") or "openclaw-weixin"),
                skill=str(payload.get("skill") or "digest"),
                run_id=payload.get("run_id"),
                subject=payload.get("subject"),
                day=payload.get("day"),
            )
        return str(entry.id)

    return asyncio.run(_run()), None


def writeback_shell_event(cfg: dict, payload: dict) -> tuple[str | None, str | None]:
    if cfg.get("_skip_writeback"):
        return None, None
    gotit = cfg.get("gotit") or {}
    api_url = (gotit.get("api_url") or "").strip()
    try:
        if api_url:
            return _writeback_rest(api_url, payload)
        return _writeback_db(payload)
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def push_plan_to_reminders(day: date, *, dry_run: bool = False) -> str | None:
    """gotit plan → Apple Reminders for ``day``. Returns error text or None."""
    if dry_run:
        return None
    try:
        from gotit.bridge.reminders import push_day

        return push_day(day, reconcile=True)
    except Exception as exc:  # noqa: BLE001
        return str(exc)


def import_reminders_to_gotit() -> str | None:
    try:
        from gotit.bridge.reminders import import_reminders

        return import_reminders(apply=True)
    except Exception as exc:  # noqa: BLE001
        return str(exc)


def build_digest(cfg: dict, mode: str, now: datetime) -> str:
    news_items: list[dict] = []
    news_errors: list[str] = []
    plan_picks: list[str] = []
    body = ""
    notes_open_url = (cfg.get("notes_open_url") or "").strip() or None
    reminder_err: str | None = None
    plan_err: str | None = None

    if mode == "morning":
        # Soft bi-di: phone edits → gotit first, then gotit truth → Reminders.
        if not cfg.get("_skip_reminders"):
            imp_err = import_reminders_to_gotit()
            if imp_err:
                news_errors.append(f"import: {imp_err}")
        plan_day = now.date()
        plan, plan_err = load_plan(cfg, plan_day)
        body, plan_picks = format_morning_plan(
            plan, plan_err, now=now, notes_open_url=notes_open_url
        )
        if not cfg.get("_skip_reminders"):
            reminder_err = push_plan_to_reminders(plan_day)
    elif mode == "evening":
        plan_day = now.date() + timedelta(days=1)
        plan, plan_err = load_plan(cfg, plan_day)
        body, plan_picks = format_evening_tomorrow(
            plan,
            plan_err,
            tomorrow=plan_day,
            now=now,
            notes_open_url=notes_open_url,
        )
        if plan_picks and not cfg.get("_skip_reminders"):
            reminder_err = push_plan_to_reminders(plan_day)
    elif mode == "news":
        news_items, news_errors = collect_items(cfg)
        body = format_news(
            news_items,
            news_errors,
            heading="🐱 Tom 资讯 · AI 摘录",
            now=now,
        )
    else:
        raise ValueError(f"unknown mode: {mode}")

    run_id = __import__("os").environ.get("OPENCLAW_CRON_RUN_ID") or None
    if mode == "morning":
        day_s = now.date().isoformat()
    elif mode == "evening":
        day_s = (now.date() + timedelta(days=1)).isoformat()
    else:
        day_s = now.date().isoformat()
    subject: str | None = None
    if plan_picks:
        subject = plan_picks[0]
    elif mode == "news" and news_items:
        subject = str(news_items[0].get("title") or "").strip() or None
    errors = list(news_errors)
    if reminder_err:
        errors.append(f"reminders: {reminder_err}")

    # Skip empty plan digests in「动态」(still deliver WeChat body).
    skip_writeback = bool(cfg.get("_skip_writeback"))
    if (
        mode in {"morning", "evening"}
        and not plan_picks
        and not plan_err
        and not reminder_err
        and not cfg.get("_force_writeback")
    ):
        skip_writeback = True

    payload = {
        "job": mode,
        "day": day_s,
        "subject": subject,
        "items": _items_payload(news_items),
        "due_summary": plan_picks,
        "errors": errors,
        "delivery_ok": None,
        "channel": "openclaw-weixin",
        "skill": "digest",
        "run_id": run_id,
    }
    event_id, wb_err = (None, None)
    if not skip_writeback:
        event_id, wb_err = writeback_shell_event(cfg, payload)

    if mode == "news":
        tip = f"\n{_WX_BLANK}\n回「这篇有用」+ 序号即可。\n"
        if event_id:
            tip += f"event_id={event_id}\n"
    else:
        tip = ""
        if reminder_err:
            tip += f"\n{_WX_BLANK}\n提醒事项同步失败：{reminder_err}\n"
        if wb_err:
            tip += f"\n{_WX_BLANK}\n写回失败：{wb_err}\n"
    return body.rstrip() + tip


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gotit OpenClaw digest v2")
    parser.add_argument("mode", choices=("morning", "evening", "news"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument(
        "--no-writeback",
        action="store_true",
        help="Skip gotit shell_event writeback (debug)",
    )
    parser.add_argument(
        "--no-remote-prefs",
        action="store_true",
        help="Ignore gotit digest_prefs; use file config only",
    )
    args = parser.parse_args(argv)

    file_cfg = _load_config(args.config)
    cfg = file_cfg if args.no_remote_prefs else merge_prefs(file_cfg)
    if args.no_writeback:
        cfg = {**cfg, "_skip_writeback": True}

    tz_name = cfg.get("timezone") or "Asia/Shanghai"
    now = datetime.now(ZoneInfo(tz_name))
    sys.stdout.write(build_digest(cfg, args.mode, now))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
