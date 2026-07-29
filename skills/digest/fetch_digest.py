#!/usr/bin/env python3
"""OpenClaw digest helper: RSS briefs + optional gotit_today excerpt.

Usage:
  python skills/digest/fetch_digest.py morning
  python skills/digest/fetch_digest.py evening

Prefer: uv run --directory <gotit-ai> python skills/digest/fetch_digest.py evening
so evening mode can import gotit.db when REST is unset.
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
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

USER_AGENT = "GotitDigest/0.1 (+https://github.com/gotit-ai; OpenClaw skill)"
DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.json")
TIMEOUT_S = 12


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
    # RSS 2.0
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

    # Atom
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
    for feed in cfg.get("feeds") or []:
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
        # newest first within feed
        def _sort_key(x: dict) -> datetime:
            pub = x["published"]
            if pub is None:
                return datetime.min.replace(tzinfo=ZoneInfo("UTC"))
            if pub.tzinfo is None:
                return pub.replace(tzinfo=ZoneInfo("UTC"))
            return pub

        parsed.sort(key=_sort_key, reverse=True)
        buckets.append(parsed)

    # Round-robin across healthy feeds for diversity
    picked: list[dict] = []
    seen_titles: set[str] = set()
    limit = int(cfg.get("item_count") or 5)
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
        lines.append("资讯抓取失败，今日无摘要。")
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


def _today_via_rest(api_url: str) -> dict | None:
    base = api_url.rstrip("/")
    # Prefer env key; never hardcode secrets in repo.
    import os

    key = os.environ.get("GOTIT_API_KEY", "").strip()
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(f"{base}/v1/today", headers=headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _today_via_db() -> dict | None:
    """Load gotit_today through domain ops (same as MCP)."""
    import asyncio

    async def _run() -> dict:
        from gotit.db.ops import get_today
        from gotit.db.runtime import ensure_db
        from gotit.db.session import session_scope

        await ensure_db()
        async with session_scope() as session:
            view = await get_today(session)
        return view.model_dump(mode="json")

    return asyncio.run(_run())


def load_today(cfg: dict) -> tuple[dict | None, str | None]:
    gotit = cfg.get("gotit") or {}
    api_url = (gotit.get("api_url") or "").strip()
    if api_url:
        try:
            return _today_via_rest(api_url), None
        except Exception as exc:  # noqa: BLE001 — surface to digest text
            return None, f"REST /v1/today 失败: {exc}"
    try:
        return _today_via_db(), None
    except Exception as exc:  # noqa: BLE001
        return None, f"db gotit_today 失败: {exc}"


def format_due(today: dict | None, err: str | None) -> tuple[str, list[str]]:
    lines = ["【今日待检】"]
    picks: list[str] = []
    if err:
        lines.append(f"无法读取 gotit_today：{err}")
        lines.append("（请确认 Postgres / uv 环境；或在 config.json 设 gotit.api_url）")
        return "\n".join(lines), picks

    assert today is not None
    day = today.get("date") or ""
    lines[0] = f"【今日待检 · {day}】"

    due = list(today.get("due_claims") or [])
    plan_items = list((today.get("plan") or {}).get("items") or [])

    seen: set[str] = set()

    def _add(text: str) -> bool:
        key = text.casefold()
        if not text or key in seen:
            return False
        seen.add(key)
        picks.append(text)
        return True

    for c in due:
        _add((c.get("text") or "").strip())
        if len(picks) >= 3:
            break
    if len(picks) < 3:
        for it in plan_items:
            status = (it.get("status") or "").lower()
            if status in {"done", "passed", "cancelled", "canceled", "skipped"}:
                continue
            _add((it.get("title") or "").strip())
            if len(picks) >= 3:
                break

    if not picks:
        lines.append("今日无待检。")
    else:
        for i, text in enumerate(picks, 1):
            lines.append(f"{i}. {_truncate(text, 100)}")
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
            )
        return str(entry.id)

    return asyncio.run(_run()), None


def writeback_shell_event(cfg: dict, payload: dict) -> tuple[str | None, str | None]:
    """Return (event_id, error). Prefer REST when api_url set."""
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


def build_digest(cfg: dict, mode: str, now: datetime) -> str:
    items, errors = collect_items(cfg)
    heading = (
        "🐱 Tom 早报 · 科技/创投摘录"
        if mode == "morning"
        else "🐱 Tom 晚报 · 简要回顾"
    )
    news = format_news(items, errors, heading=heading, now=now)
    due_picks: list[str] = []
    body = news
    if mode == "evening":
        today, err = load_today(cfg)
        due_text, due_picks = format_due(today, err)
        body = news + "\n" + due_text

    run_id = __import__("os").environ.get("OPENCLAW_CRON_RUN_ID") or None
    payload = {
        "job": mode,
        "items": _items_payload(items),
        "due_summary": due_picks,
        "errors": errors,
        "delivery_ok": None,
        "channel": "openclaw-weixin",
        "skill": "digest",
        "run_id": run_id,
    }
    event_id, wb_err = writeback_shell_event(cfg, payload)

    if mode == "morning":
        tip = "\n回「这篇有用」+ 序号，我只记一笔 interest（不做完整 ingest）。\n"
    else:
        tip = "\n回「这篇有用」+ 序号 → gotit_record_interest；待检请走 gotit examine。\n"
    if event_id:
        tip += f"event_id={event_id}\n"
    if wb_err:
        tip += f"写回 gotit 失败（观测缺口）：{wb_err}\n"
    return body + tip


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gotit OpenClaw digest")
    parser.add_argument("mode", choices=("morning", "evening"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument(
        "--no-writeback",
        action="store_true",
        help="Skip gotit shell_event writeback (debug)",
    )
    args = parser.parse_args(argv)

    cfg = _load_config(args.config)
    if args.no_writeback:
        cfg = {**cfg, "_skip_writeback": True}

    tz_name = cfg.get("timezone") or "Asia/Shanghai"
    now = datetime.now(ZoneInfo(tz_name))
    sys.stdout.write(build_digest(cfg, args.mode, now))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
