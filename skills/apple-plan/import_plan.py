#!/usr/bin/env python3
"""Import Apple Reminders / Notes into gotit daily plan items.

Usage (default = dry-run):
  uv run python skills/apple-plan/import_plan.py reminders --list "学习计划"
  uv run python skills/apple-plan/import_plan.py reminders --list "学习计划" --apply
  uv run python skills/apple-plan/import_plan.py notes --title "学习计划" --apply
  uv run python skills/apple-plan/import_plan.py notes --file ./plan.md --dry-run
  uv run python skills/apple-plan/import_plan.py push --day 2026-07-30 --apply
  uv run python skills/apple-plan/import_plan.py rm --day 2026-07-30 --title "刷 DP" --apply

Writes via REST (/v1/days/{day}/plan) or db.ops (same as MCP). Never imports
AppleScript into gotit core.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# Allow `from parse import ...` when run as a script.
_SKILL_DIR = Path(__file__).resolve().parent
if str(_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(_SKILL_DIR))

from parse import (  # noqa: E402
    MergeRow,
    NotesParseError,
    PlanDraft,
    merge_with_existing,
    parse_notes_body,
    parse_time_hint,
    reminders_to_drafts,
    summarize_merge,
)

USER_AGENT = "GotitApplePlan/0.1 (+OpenClaw skill)"
DEFAULT_CONFIG = _SKILL_DIR / "config.json"
TIMEOUT_S = 20


def _load_config(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _run_jxa(script: Path, args: list[str]) -> dict:
    cmd = ["osascript", "-l", "JavaScript", str(script), *args]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except FileNotFoundError as exc:
        raise SystemExit(
            "找不到 osascript（仅 macOS）。Apple 访问必须在本机 OpenClaw skill 执行。"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise SystemExit("osascript 超时：备忘录/提醒事项可能卡在权限对话框。") from exc

    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if not out:
        msg = err or f"osascript 无输出（exit {proc.returncode}）"
        raise SystemExit(
            f"Apple 读取失败：{msg}\n"
            "请检查 系统设置 → 隐私与安全性 → 提醒事项 / 自动化。"
        )
    try:
        data = json.loads(out)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"JXA 返回非 JSON：{out[:200]!r}") from exc
    if not data.get("ok"):
        raise SystemExit(str(data.get("error") or "Apple 读取失败"))
    return data


def _api_headers() -> dict[str, str]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    key = os.environ.get("GOTIT_API_KEY", "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


def _get_plan_rest(api_url: str, day: date) -> list[dict]:
    base = api_url.rstrip("/")
    req = urllib.request.Request(
        f"{base}/v1/days/{day.isoformat()}/plan",
        headers=_api_headers(),
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return list(data.get("items") or [])


def _create_plan_rest(api_url: str, day: date, title: str) -> dict:
    base = api_url.rstrip("/")
    body = json.dumps(
        {"title": title, "source": "manual", "status": "planned"}
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/v1/days/{day.isoformat()}/plan/items",
        data=body,
        headers=_api_headers(),
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_plan_db(day: date) -> list[dict]:
    import asyncio

    async def _run() -> list[dict]:
        from gotit.db.ops import get_plan
        from gotit.db.runtime import ensure_db
        from gotit.db.session import session_scope

        await ensure_db()
        async with session_scope() as session:
            view = await get_plan(session, day)
        return [i.model_dump(mode="json") for i in view.items]

    return asyncio.run(_run())


def _create_plan_db(day: date, title: str) -> dict:
    import asyncio

    async def _run() -> dict:
        from gotit.core.models import PlanItemSource, PlanItemStatus
        from gotit.db.ops import upsert_plan_item
        from gotit.db.runtime import ensure_db
        from gotit.db.session import session_scope

        await ensure_db()
        async with session_scope() as session:
            view = await upsert_plan_item(
                session,
                day,
                title=title,
                source=PlanItemSource.MANUAL,
                status=PlanItemStatus.PLANNED,
            )
        return view.model_dump(mode="json")

    return asyncio.run(_run())


def _delete_plan_rest(api_url: str, item_id: str) -> None:
    base = api_url.rstrip("/")
    req = urllib.request.Request(
        f"{base}/v1/plan/items/{item_id}",
        headers=_api_headers(),
        method="DELETE",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        resp.read()


def _delete_plan_db(item_id: str) -> None:
    import asyncio
    from uuid import UUID

    async def _run() -> None:
        from gotit.db.ops import delete_plan_item
        from gotit.db.runtime import ensure_db
        from gotit.db.session import session_scope

        await ensure_db()
        async with session_scope() as session:
            await delete_plan_item(session, UUID(item_id))

    asyncio.run(_run())


def _find_plan_items(api_url: str, day: date, title: str) -> list[dict]:
    items = _get_plan_rest(api_url, day) if api_url else _get_plan_db(day)
    needle = title.strip().casefold()
    return [
        i
        for i in items
        if (i.get("title") or "").strip().casefold() == needle
    ]


class GotitPlanClient:
    def __init__(self, api_url: str = "") -> None:
        self.api_url = (api_url or "").strip()

    def titles_for_day(self, day: date) -> set[str]:
        try:
            items = (
                _get_plan_rest(self.api_url, day)
                if self.api_url
                else _get_plan_db(day)
            )
        except Exception as exc:  # noqa: BLE001 — surface readable error
            raise RuntimeError(
                f"读取 gotit 计划失败（{day.isoformat()}）：{exc}。"
                "请确认 Postgres / `uv run gotit-api`，"
                "或在 config.json 设置 gotit.api_url + GOTIT_API_KEY。"
            ) from exc
        return {(i.get("title") or "").strip().casefold() for i in items if i.get("title")}

    def create(self, day: date, title: str) -> None:
        try:
            if self.api_url:
                _create_plan_rest(self.api_url, day, title)
            else:
                _create_plan_db(day, title)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"写入 plan_item 失败 HTTP {exc.code}：{detail}"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"写入 plan_item 失败：{exc}") from exc


def _filter_drafts_by_range(
    drafts: list[PlanDraft],
    date_from: date | None,
    date_to: date | None,
) -> list[PlanDraft]:
    out: list[PlanDraft] = []
    for d in drafts:
        if date_from is not None and d.day < date_from:
            continue
        if date_to is not None and d.day > date_to:
            continue
        out.append(d)
    return out


def _build_existing(
    client: GotitPlanClient,
    drafts: list[PlanDraft],
    *,
    soft: bool,
) -> tuple[dict[date, set[str]], list[str]]:
    by_day: dict[date, set[str]] = {}
    warnings: list[str] = []
    for day in {d.day for d in drafts}:
        try:
            by_day[day] = client.titles_for_day(day)
        except RuntimeError as exc:
            if soft:
                by_day[day] = set()
                warnings.append(
                    f"无法读取 gotit {day.isoformat()} 计划（dry-run 按全部 create 预览）：{exc}"
                )
            else:
                raise SystemExit(str(exc)) from exc
    return by_day, warnings


def _print_preview(rows: list[MergeRow], warnings: list[str], *, apply: bool) -> None:
    if warnings:
        print("—— warnings ——")
        for w in warnings:
            print(f"· {w}")
        print()
    print("day         action  title")
    print("----------  ------  -----")
    for r in rows:
        print(f"{r.day.isoformat()}  {r.action:<6}  {r.title}")
    stats = summarize_merge(rows)
    print()
    suffix = "（已准备写入）" if apply else "（dry-run，未写入）"
    print(
        f"合计 {stats['total']}：将新建 {stats['create']}，跳过 {stats['skip']}{suffix}"
    )


def _apply(client: GotitPlanClient, rows: list[MergeRow]) -> int:
    created = 0
    # Preserve sort stability: group by day, create in order.
    by_day: dict[date, list[MergeRow]] = defaultdict(list)
    for r in rows:
        if r.action == "create":
            by_day[r.day].append(r)
    for day in sorted(by_day):
        for r in by_day[day]:
            client.create(day, r.title)
            created += 1
    return created


def cmd_reminders(args: argparse.Namespace, cfg: dict) -> int:
    list_name = args.list or cfg.get("reminders_list") or "学习计划"
    data = _run_jxa(_SKILL_DIR / "fetch_reminders.jxa", [list_name])
    items = list(data.get("items") or [])
    drafts, warnings = reminders_to_drafts(
        items, date_from=args.date_from, date_to=args.date_to
    )
    if not drafts:
        for w in warnings:
            print(f"· {w}", file=sys.stderr)
        raise SystemExit(
            f"列表「{list_name}」没有可导入的提醒（需未完成且带到期日"
            f"{'，且落在 --from/--to 范围内' if args.date_from or args.date_to else ''}）。"
        )
    return _finish(args, cfg, drafts, warnings)


def cmd_notes(args: argparse.Namespace, cfg: dict) -> int:
    if args.file:
        body = Path(args.file).read_text(encoding="utf-8")
        title = args.title or Path(args.file).stem
        try:
            drafts = parse_notes_body(body, note_title=title)
        except NotesParseError as exc:
            raise SystemExit(f"Notes 解析失败：{exc}") from exc
        warnings: list[str] = []
    else:
        title_match = args.title or cfg.get("notes_title_match") or "学习计划"
        folder = args.folder if args.folder is not None else (cfg.get("notes_folder") or "")
        jxa_args = ["--title", title_match]
        if folder:
            jxa_args.extend(["--folder", folder])
        data = _run_jxa(_SKILL_DIR / "fetch_notes.jxa", jxa_args)
        notes = list(data.get("notes") or [])
        drafts = []
        warnings = []
        for note in notes:
            try:
                drafts.extend(
                    parse_notes_body(
                        str(note.get("body") or ""),
                        note_title=str(note.get("title") or title_match),
                    )
                )
            except NotesParseError as exc:
                raise SystemExit(
                    f"备忘录「{note.get('title')}」解析失败：{exc}"
                ) from exc
        if not drafts:
            raise SystemExit("匹配的备忘录没有可导入条目。")

    drafts = _filter_drafts_by_range(drafts, args.date_from, args.date_to)
    if not drafts:
        raise SystemExit("日期窗内没有可导入条目。")
    return _finish(args, cfg, drafts, warnings)


def cmd_push(args: argparse.Namespace, cfg: dict) -> int:
    """gotit plan → Apple Reminders (so iPhone 待办 can see chat-created items)."""
    list_name = args.list or cfg.get("reminders_list") or "学习计划"
    day = args.day or date.today()
    client = GotitPlanClient(
        api_url=(args.api_url or (cfg.get("gotit") or {}).get("api_url") or "")
    )
    try:
        items = (
            _get_plan_rest(client.api_url, day)
            if client.api_url
            else _get_plan_db(day)
        )
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"读取 gotit 计划失败：{exc}") from exc

    only_title = (args.title or "").strip()
    explicit_time = (args.time or "").strip() or None
    if explicit_time and not re.fullmatch(r"\d{2}:\d{2}", explicit_time):
        raise SystemExit(f"--time 须为 HH:MM，收到：{explicit_time!r}")

    payload: list[dict] = []
    for it in items:
        status = str(it.get("status") or "").lower()
        if status in {"verified", "done", "passed", "cancelled", "canceled", "skipped"}:
            continue
        title = (it.get("title") or "").strip()
        if not title:
            continue
        if only_title and title.casefold() != only_title.casefold():
            continue
        # Prefer Agent-supplied --time; regex on title is only a fallback.
        time_hm = explicit_time or parse_time_hint(title, default="09:00")
        payload.append(
            {"title": title, "due": day.isoformat(), "time": time_hm}
        )

    print(f"list={list_name}  day={day.isoformat()}  candidates={len(payload)}")
    for p in payload:
        src = "agent" if explicit_time else "title-fallback"
        print(f"  · {p['time']} ({src})  {p['title']}")
    if not payload:
        msg = "gotit 该日无开放计划，无需写回提醒事项。"
        if only_title:
            msg = f"未找到标题匹配「{only_title}」的开放计划。"
        print(msg)
        return 0

    apply = bool(args.apply) and not args.dry_run
    if not apply:
        print()
        print("（dry-run，未写入 Reminders；加 --apply 写回；会设到期提醒通知）")
        return 0

    data = _run_jxa(
        _SKILL_DIR / "create_reminders.jxa",
        [list_name, json.dumps(payload, ensure_ascii=False)],
    )
    print()
    print(
        f"提醒事项「{data.get('list') or list_name}」："
        f"新建 {data.get('created', 0)}，更新 {data.get('updated', 0)}，"
        f"跳过 {data.get('skipped', 0)}"
    )
    errs = data.get("errors") or []
    if errs:
        for e in errs:
            print(f"· {e}", file=sys.stderr)
    if not data.get("ok"):
        raise SystemExit(str(data.get("error") or "写入提醒事项失败"))
    return 0


def cmd_rm(args: argparse.Namespace, cfg: dict) -> int:
    """Delete gotit plan item(s) + matching Reminders by title."""
    list_name = args.list or cfg.get("reminders_list") or "学习计划"
    title = (args.title or "").strip()
    if not title:
        raise SystemExit("rm 需要 --title")
    day = args.day  # may be None → only delete Reminders (no day filter)
    api_url = (args.api_url or (cfg.get("gotit") or {}).get("api_url") or "").strip()
    apply = bool(args.apply) and not args.dry_run

    gotit_hits: list[dict] = []
    if day is not None:
        try:
            gotit_hits = _find_plan_items(api_url, day, title)
        except Exception as exc:  # noqa: BLE001
            raise SystemExit(f"读取 gotit 计划失败：{exc}") from exc
        print(f"gotit day={day.isoformat()}  matches={len(gotit_hits)}")
        for h in gotit_hits:
            print(f"  · {h.get('id')}  {h.get('title')}")
        if not gotit_hits:
            print(f"gotit 无匹配「{title}」（仍可删提醒事项）")
    else:
        print("gotit：未传 --day，只删提醒事项")

    print(f"reminders list={list_name}  title={title!r}  due={day.isoformat() if day else '*'}")
    if not apply:
        print()
        print("（dry-run；加 --apply 从 gotit + 提醒事项删除）")
        return 0

    deleted_gotit = 0
    for h in gotit_hits:
        iid = str(h.get("id") or "")
        if not iid:
            continue
        try:
            if api_url:
                _delete_plan_rest(api_url, iid)
            else:
                _delete_plan_db(iid)
            deleted_gotit += 1
        except Exception as exc:  # noqa: BLE001
            raise SystemExit(f"删除 gotit plan_item 失败：{exc}") from exc

    spec: dict = {"titles": [title]}
    if day is not None:
        spec["due"] = day.isoformat()
    data = _run_jxa(
        _SKILL_DIR / "delete_reminders.jxa",
        [list_name, json.dumps(spec, ensure_ascii=False)],
    )
    print()
    print(
        f"已删 gotit {deleted_gotit} 条；"
        f"提醒事项「{data.get('list') or list_name}」删除 {data.get('deleted', 0)} 条"
    )
    errs = data.get("errors") or []
    if errs:
        for e in errs:
            print(f"· {e}", file=sys.stderr)
    if not data.get("ok"):
        raise SystemExit(str(data.get("error") or "删除提醒事项失败"))
    return 0


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Apple Reminders ↔ gotit plan_items（默认 dry-run）"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="config.json path",
    )
    parser.add_argument(
        "--api-url",
        default="",
        help="gotit REST base (else config gotit.api_url or db.ops)",
    )
    parser.add_argument(
        "--from",
        dest="date_from",
        type=_parse_date,
        default=None,
        help="inclusive start day YYYY-MM-DD",
    )
    parser.add_argument(
        "--to",
        dest="date_to",
        type=_parse_date,
        default=None,
        help="inclusive end day YYYY-MM-DD",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="preview only (default unless --apply)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write changes (也可写在子命令后：… push --apply)",
    )

    sub = parser.add_subparsers(dest="cmd", required=True)

    flag_parent = argparse.ArgumentParser(add_help=False)
    flag_parent.add_argument("--dry-run", action="store_true", default=False)
    flag_parent.add_argument("--apply", action="store_true", default=False)

    p_rem = sub.add_parser(
        "reminders", parents=[flag_parent], help="从提醒事项列表 → gotit"
    )
    p_rem.add_argument("--list", default="", help='列表名，默认「学习计划」')

    p_notes = sub.add_parser(
        "notes", parents=[flag_parent], help="从备忘录导入（次要）"
    )
    p_notes.add_argument("--title", default="", help="标题包含匹配（默认「学习计划」）")
    p_notes.add_argument("--folder", default=None, help="限定文件夹名")
    p_notes.add_argument(
        "--file",
        type=Path,
        default=None,
        help="从本地 markdown 文件解析（跳过 Notes.app，便于测试）",
    )

    p_push = sub.add_parser(
        "push",
        parents=[flag_parent],
        help="gotit 日计划 → 提醒事项（对话建计划后写回 iPhone 待办）",
    )
    p_push.add_argument(
        "--day",
        type=date.fromisoformat,
        default=None,
        help="YYYY-MM-DD（默认今天）",
    )
    p_push.add_argument("--list", default="", help='列表名，默认「学习计划」')
    p_push.add_argument(
        "--title",
        default="",
        help="只同步该标题（与 gotit plan 匹配）；Agent 新建单条后用",
    )
    p_push.add_argument(
        "--time",
        default="",
        help="HH:MM，由 Agent 从用户话里理解后传入；不填才回退解析标题",
    )

    p_rm = sub.add_parser(
        "rm",
        parents=[flag_parent],
        help="按标题删除 gotit 计划 + 提醒事项（对话「删除…」）",
    )
    p_rm.add_argument(
        "--day",
        type=date.fromisoformat,
        default=None,
        help="YYYY-MM-DD（有则删 gotit 该日条目，并按到期日过滤提醒）",
    )
    p_rm.add_argument("--title", required=True, help="计划标题（casefold 精确匹配）")
    p_rm.add_argument("--list", default="", help='列表名，默认「学习计划」')

    args = parser.parse_args(argv)
    cfg = _load_config(args.config)

    tz = cfg.get("timezone") or "Asia/Shanghai"
    print(f"# apple-plan · {datetime.now(ZoneInfo(tz)).strftime('%Y-%m-%d %H:%M %Z')}")
    print(f"# mode={'apply' if args.apply and not args.dry_run else 'dry-run'}")
    print()

    if args.cmd == "reminders":
        return cmd_reminders(args, cfg)
    if args.cmd == "notes":
        return cmd_notes(args, cfg)
    if args.cmd == "push":
        return cmd_push(args, cfg)
    if args.cmd == "rm":
        return cmd_rm(args, cfg)
    raise SystemExit(f"unknown cmd: {args.cmd}")


def _finish(
    args: argparse.Namespace,
    cfg: dict,
    drafts: list[PlanDraft],
    warnings: list[str],
) -> int:
    gotit = cfg.get("gotit") or {}
    api_url = (args.api_url or gotit.get("api_url") or "").strip()
    client = GotitPlanClient(api_url)
    apply = bool(args.apply) and not bool(args.dry_run)
    existing, read_warnings = _build_existing(client, drafts, soft=not apply)
    warnings = [*warnings, *read_warnings]
    rows = merge_with_existing(drafts, existing)

    _print_preview(rows, warnings, apply=apply)
    if not apply:
        return 0

    try:
        created = _apply(client, rows)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    skipped = sum(1 for r in rows if r.action == "skip")
    print()
    print(f"已写入 gotit：新建 {created}，跳过 {skipped}。")
    print("（gotit 为日计划真源；可用 push --apply 同步到提醒事项。）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
