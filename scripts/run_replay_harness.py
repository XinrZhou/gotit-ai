#!/usr/bin/env python
"""Run Verify Spine replay / holdout harness (no live LLM).

Usage:
    uv run python scripts/run_replay_harness.py [--set replay|holdout] [--label LABEL]

Exit code 0 if all cases pass, 1 otherwise.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from gotit.db import session_scope
from gotit.db.runtime import ensure_db
from gotit.harness import SUITE_VERSION, run_harness
from gotit.harness.cases.holdout import build_holdout_cases
from gotit.harness.cases.replay import build_replay_cases


async def main(*, case_set: str, label: str | None) -> int:
    await ensure_db()
    async with session_scope() as session:
        if case_set == "holdout":
            cases = build_holdout_cases(session)
        else:
            cases = build_replay_cases(session)
        run = await run_harness(session, cases, case_set=case_set, label=label)
        await session.commit()

    print(f"harness run {run.id}")
    print(f"  case_set      : {run.case_set}")
    print(f"  suite_version : {(run.summary or {}).get('suite_version', SUITE_VERSION)}")
    print(f"  verdict       : {run.verdict}")
    print(f"  summary       : {run.summary}")
    return 0 if run.verdict == "pass" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Replay/holdout harness for Verify Spine contracts (no LLM)."
    )
    parser.add_argument(
        "--set",
        dest="case_set",
        choices=("replay", "holdout"),
        default="replay",
        help="case set to run (default: replay)",
    )
    parser.add_argument("--label", default=None)
    args = parser.parse_args()
    sys.exit(asyncio.run(main(case_set=args.case_set, label=args.label)))
