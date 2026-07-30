#!/usr/bin/env python
"""Run the personal-gold harness set and print a compare table.

Usage:
    uv run python scripts/run_gold_compare.py [--label LABEL]

Exit 0 if all gold cases pass. See notes-gold.md for the log template.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date

from gotit.db import session_scope
from gotit.db.runtime import ensure_db
from gotit.harness import run_harness
from gotit.harness.cases.gold import build_gold_cases, compare_rows_from_gate_pairs


def _print_table(label: str | None) -> None:
    today = date.today().isoformat()
    print(f"# gold 对照 · {today}")
    print(f"label: {label or '(none)'}")
    print()
    headers = ("日期", "claim", "examine", "critic", "gate", "分歧?", "备注")
    print("| " + " | ".join(headers) + " |")
    print("| " + " | ".join("---" for _ in headers) + " |")
    for row in compare_rows_from_gate_pairs():
        print(
            "| "
            + " | ".join(
                [
                    today,
                    row["claim"],
                    row["examine"],
                    row["critic"],
                    row["gate"],
                    row["diverge"],
                    row["note"],
                ]
            )
            + " |"
        )
    print()


async def main(label: str | None) -> int:
    _print_table(label)
    await ensure_db()
    async with session_scope() as session:
        cases = build_gold_cases(session)
        run = await run_harness(session, cases, case_set="gold", label=label)
        await session.commit()

    print(f"harness run {run.id}")
    print(f"  case_set : {run.case_set}")
    print(f"  verdict  : {run.verdict}")
    print(f"  summary  : {run.summary}")
    if run.verdict != "pass":
        print("FAIL — gate formula or retest conversion drifted; do not ignore.")
        return 1
    print("OK — copy the table above into docs/gold-logs/ if recording a before/after.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default=None)
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.label)))
