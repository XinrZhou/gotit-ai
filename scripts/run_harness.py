#!/usr/bin/env python
"""Run the dev harness case set and print a baseline verdict.

Usage:
    uv run python scripts/run_harness.py [--label LABEL]

Exit code 0 if all cases pass, 1 otherwise.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from gotit.db import session_scope
from gotit.db.runtime import ensure_db
from gotit.harness import run_harness
from gotit.harness.cases.dev import build_dev_cases


async def main(label: str | None) -> int:
    await ensure_db()
    async with session_scope() as session:
        cases = build_dev_cases(session)
        run = await run_harness(session, cases, case_set="dev", label=label)
        await session.commit()

    print(f"harness run {run.id}")
    print(f"  case_set : {run.case_set}")
    print(f"  verdict  : {run.verdict}")
    print(f"  summary  : {run.summary}")
    return 0 if run.verdict == "pass" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default=None)
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.label)))
