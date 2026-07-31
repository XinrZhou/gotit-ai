#!/usr/bin/env python3
"""List due interview reminders and/or ramp nudges; --apply marks them."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from uuid import UUID


def format_reminder(item: dict) -> str:
    company = item.get("company") or "?"
    role = item.get("role_title") or "?"
    when = item.get("scheduled_at") or "?"
    round_ = item.get("round") or "—"
    offset = item.get("offset_hours")
    lines = [
        f"面试提醒 · {company} · {role}",
        f"时间：{when}",
        f"轮次：{round_}",
    ]
    if offset is not None:
        lines.append(f"节点：T{int(offset):+d}h")
    return "\n".join(lines)


def format_ramp(item: dict) -> str:
    company = item.get("company") or "?"
    role = item.get("role_title") or "?"
    hours = item.get("hours_until")
    hint = item.get("tier_hint") or ""
    action = item.get("suggest_action") or ""
    hours_s = f"{float(hours):.0f}" if hours is not None else "?"
    lines = [
        f"面试临近 · {company} · {role}",
        f"约 {hours_s}h 后" + (f" · {hint}" if hint else ""),
    ]
    if action:
        lines.append(str(action))
    return "\n".join(lines)


async def _run(*, apply: bool, as_json: bool, ramp: bool, offsets: bool) -> int:
    from gotit.db.ops import (
        list_due_interview_reminders,
        list_interview_ramp_nudges,
        mark_interview_ramp_nudged,
        mark_interview_reminded,
    )
    from gotit.db.runtime import ensure_db
    from gotit.db.session import session_scope

    await ensure_db()
    now = datetime.now(UTC)
    async with session_scope() as session:
        due = (
            await list_due_interview_reminders(session, now=now, user_id="local")
            if offsets
            else []
        )
        nudges = (
            await list_interview_ramp_nudges(session, now=now, user_id="local")
            if ramp
            else []
        )
        if as_json:
            print(
                json.dumps(
                    {
                        "reminders": [d.model_dump(mode="json") for d in due],
                        "ramp_nudges": [n.model_dump(mode="json") for n in nudges],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        if not due and not nudges:
            print("无到期面试提醒 / 升温 nudge。")
            return 0
        for d in due:
            dump = d.model_dump(mode="json")
            print("---")
            print(format_reminder(dump))
            iid = dump.get("interview_id")
            if apply and iid:
                await mark_interview_reminded(
                    session, UUID(str(iid)), user_id="local", at=now
                )
                print(f"marked reminded id={iid}")
        for n in nudges:
            dump = n.model_dump(mode="json")
            print("---")
            print(format_ramp(dump))
            iid = dump.get("interview_id")
            if apply and iid:
                await mark_interview_ramp_nudged(
                    session, UUID(str(iid)), user_id="local", at=now
                )
                print(f"marked ramp-nudged id={iid}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument(
        "--ramp",
        action="store_true",
        help="Include P4 countdown ramp nudges (default: with offsets unless --offsets-only)",
    )
    p.add_argument(
        "--offsets-only",
        action="store_true",
        help="Only P3d offset reminders (skip ramp)",
    )
    p.add_argument(
        "--ramp-only",
        action="store_true",
        help="Only P4 ramp nudges",
    )
    args = p.parse_args(argv)
    offsets = not args.ramp_only
    ramp = not args.offsets_only
    if args.ramp:
        ramp = True
    if args.offsets_only:
        offsets = True
        ramp = False
    if args.ramp_only:
        offsets = False
        ramp = True
    return asyncio.run(
        _run(apply=bool(args.apply), as_json=bool(args.json), ramp=ramp, offsets=offsets)
    )


if __name__ == "__main__":
    sys.exit(main())
