#!/usr/bin/env python3
"""Inject OpenSpec workflow context at session start (no follow-up loop)."""

from __future__ import annotations

import json
import sys

CONTEXT = """\
# OpenSpec (non-trivial work)

For behavior/API/schema/product changes:
1. Use `openspec/changes/<name>/` (proposal.md, design.md, tasks.md).
2. Check off tasks while implementing.
3. Sync/archive OpenSpec when the change is ready to keep — typically \
before `git commit` or opening a PR (a hook may ask/deny commit if code \
changed without OpenSpec updates).
4. Skip OpenSpec only for trivial typos/comments/tiny docs.

Read `openspec/config.yaml` and `AGENTS.md`. Optional slash commands after \
`openspec init --tools cursor`: `/opsx-propose`, `/opsx-apply`, `/opsx-archive`.
"""


def main() -> None:
    try:
        sys.stdin.read()
    except Exception:
        pass
    print(json.dumps({"additional_context": CONTEXT}))


if __name__ == "__main__":
    main()
