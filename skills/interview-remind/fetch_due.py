#!/usr/bin/env python3
"""List due interview reminders; --apply marks them reminded."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from uuid import UUID


def format_msg(item: dict) -> str:
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


async def _run(*, apply: bool, as_json: bool) -> int:
    from gotit.db.ops import list_due_interview_reminders, mark_interview_reminded
    from gotit.db.runtime import ensure_db
    from gotit.db.session import session_scope

    await ensure_db()
    now = datetime.now(UTC)
    async with session_scope() as session:
        due = await list_due_interview_reminders(session, now=now, user_id="local")
        if as_json:
            print(
                json.dumps(
                    [d.model_dump(mode="json") for d in due],
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        if not due:
            print("无到期面试提醒。")
            return 0
        for d in due:
            dump = d.model_dump(mode="json")
            print("---")
            print(format_msg(dump))
            iid = dump.get("interview_id")
            if apply and iid:
                await mark_interview_reminded(
                    session, UUID(str(iid)), user_id="local", at=now
                )
                print(f"marked reminded id={iid}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    return asyncio.run(_run(apply=bool(args.apply), as_json=bool(args.json)))


if __name__ == "__main__":
    sys.exit(main())
