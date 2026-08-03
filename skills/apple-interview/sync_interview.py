#!/usr/bin/env python3
"""CLI: upsert/rm gotit interviews ↔ Apple Calendar (JXA)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
JXA = ROOT / "sync_calendar.jxa"
CONFIG_PATH = ROOT / "config.json"


def _load_config() -> dict:
    if not CONFIG_PATH.is_file():
        return {
            "calendar_name": "面试",
            "default_duration_minutes": 60,
        }
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _run_jxa(cal_name: str, payload: dict) -> dict:
    if not JXA.is_file():
        return {"ok": False, "error": f"missing {JXA}"}
    proc = subprocess.run(
        ["osascript", "-l", "JavaScript", str(JXA), cal_name, json.dumps(payload)],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    out = (proc.stdout or "").strip()
    if not out:
        err = (proc.stderr or "").strip()
        return {
            "ok": False,
            "error": err[-500:] or f"osascript exit {proc.returncode}",
        }
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {"ok": False, "error": out[-500:]}


def _parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def cmd_upsert(args: argparse.Namespace) -> int:
    cfg = _load_config()
    cal = args.calendar or cfg.get("calendar_name") or "面试"
    duration = int(cfg.get("default_duration_minutes") or 60)
    start = _parse_iso(args.start)
    end = start + timedelta(minutes=duration)
    alarms = []
    if args.alarms:
        alarms = [int(x) for x in args.alarms.split(",") if x.strip()]
    payload = {
        "op": "upsert",
        "id": args.id,
        "title": args.title,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "notes": args.notes or "",
        "alarms_hours_before": alarms,
    }
    result = _run_jxa(cal, payload)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


def cmd_rm(args: argparse.Namespace) -> int:
    cfg = _load_config()
    cal = args.calendar or cfg.get("calendar_name") or "面试"
    result = _run_jxa(cal, {"op": "rm", "id": args.id})
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="gotit interview ↔ Apple Calendar")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_up = sub.add_parser("upsert", help="Create/update Calendar event")
    p_up.add_argument("--id", required=True)
    p_up.add_argument("--title", required=True)
    p_up.add_argument("--start", required=True, help="ISO-8601 datetime")
    p_up.add_argument("--notes", default="")
    p_up.add_argument(
        "--alarms",
        default="24,2",
        help="Comma-separated hours-before alarms (default 24,2)",
    )
    p_up.add_argument("--calendar", default="")
    p_up.set_defaults(func=cmd_upsert)

    p_rm = sub.add_parser("rm", help="Remove Calendar event by interview id")
    p_rm.add_argument("--id", required=True)
    p_rm.add_argument("--calendar", default="")
    p_rm.set_defaults(func=cmd_rm)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
