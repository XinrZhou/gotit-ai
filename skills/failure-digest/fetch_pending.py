#!/usr/bin/env python3
"""Print pending failure digests (dry-run). Mark with --apply after send."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys


def _verdict_zh(v: str) -> str:
    return {"almost": "差一点", "owe_next": "下次再来"}.get(v, v)


def format_msg(entry: dict) -> str:
    c = entry.get("content") or {}
    claim = (c.get("claim_text") or "").strip() or "(无 claim 摘要)"
    verdict = _verdict_zh(str(c.get("verdict") or ""))
    follow = (c.get("follow_up") or "").strip()
    lines = [
        f"挂题复盘 · {verdict}",
        f"「{claim}」",
    ]
    if follow:
        lines.append(follow)
    lines.append("再检：打开 gotit 考我，或回「再考这条」。")
    return "\n".join(lines)


async def _run(*, apply: bool) -> int:
    from gotit.db.ops import list_pending_failure_digests, mark_failure_digest_notified
    from gotit.db.runtime import ensure_db
    from gotit.db.session import session_scope

    await ensure_db()
    async with session_scope() as session:
        pending = await list_pending_failure_digests(session, user_id="local", limit=20)
        if not pending:
            print("无待推送挂题复盘。")
            return 0
        for e in pending:
            dump = e.model_dump(mode="json")
            print("---")
            print(format_msg(dump))
            print(f"id={e.id}")
            if apply:
                await mark_failure_digest_notified(session, e.id, user_id="local")
                print("marked notified")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--apply",
        action="store_true",
        help="mark pending as notified (use after WeChat delivery)",
    )
    p.add_argument("--json", action="store_true", help="dump raw JSON")
    args = p.parse_args(argv)

    async def _json() -> int:
        from gotit.db.ops import list_pending_failure_digests
        from gotit.db.runtime import ensure_db
        from gotit.db.session import session_scope

        await ensure_db()
        async with session_scope() as session:
            pending = await list_pending_failure_digests(
                session, user_id="local", limit=20
            )
        print(
            json.dumps(
                [e.model_dump(mode="json") for e in pending],
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.json:
        return asyncio.run(_json())
    return asyncio.run(_run(apply=bool(args.apply)))


if __name__ == "__main__":
    sys.exit(main())
