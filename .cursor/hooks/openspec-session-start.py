#!/usr/bin/env python3
"""Inject OpenSpec + SYSTEM.md pointer at session start (token-cheap onboarding)."""

from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SYSTEM = REPO / "docs" / "SYSTEM.md"

# Keep injection small — agents should Read docs/SYSTEM.md for full snapshot.
CONTEXT = """\
# Gotit session context

## Onboarding (do this first)
- Read `docs/SYSTEM.md` for architecture, stack, shipped features, layout.
- Read `docs/PRODUCT.md` before expanding features (positioning + intake rules).
- Product: daily learning companion; chat owns the surface; verify is the spine.
- Stack: Python 3.12 + uv + FastAPI + MCP; React/Vite/npm; Postgres (Redis unused).
- Deploy: personal / single-user (`GOTIT_USER_ID` + API key); not multi-tenant.
- Iron: `gotit.core` framework-free; REST↔MCP share `db.ops`; gate is code not LLM.

## OpenSpec (non-trivial work)
1. Before a new change: scan active `openspec/changes/*/` — merge if same
   subdomain / UI surface / follow-up of an open proposal; else new folder.
2. Use `proposal.md` / `design.md` / `tasks.md`; check off while implementing.
3. Sync/archive before commit/PR (hook may ask if code changed without OpenSpec).
4. Skip only for trivial typos/comments/tiny docs. See `.cursor/rules/openspec.mdc`.

## Doc sync (before commit/PR)
If the change alters product behavior, APIs, architecture, or user-facing story:
update `docs/SYSTEM.md`, and `README.md` / `README.zh-CN.md` when the human
pitch or quick start drifts. Positioning / feature intake → `docs/PRODUCT.md`.
A commit hook may ask when code changed without those docs.

## AI Coding practice
On commit: if the session taught a reusable system-building practice, update
`/Users/zxr/personal/Agent-项目/AI-Coding工程实践.md` and
`.cursor/rules/ai-coding-practice.mdc`. See that rule for the checklist.

See `openspec/config.yaml`, `AGENTS.md`, `docs/SYSTEM.md`, `docs/PRODUCT.md`.
"""


def _system_excerpt(max_chars: int = 1200) -> str:
    if not SYSTEM.is_file():
        return ""
    text = SYSTEM.read_text(encoding="utf-8")
    # Prefer body after title; cap size for token budget.
    body = text.strip()
    if len(body) <= max_chars:
        return body
    return body[: max_chars - 20].rstrip() + "\n\n…(see docs/SYSTEM.md)"


def main() -> None:
    with contextlib.suppress(Exception):
        sys.stdin.read()
    extra = _system_excerpt()
    ctx = CONTEXT
    if extra:
        ctx = f"{CONTEXT}\n## SYSTEM.md excerpt\n\n{extra}\n"
    print(json.dumps({"additional_context": ctx}))


if __name__ == "__main__":
    main()
