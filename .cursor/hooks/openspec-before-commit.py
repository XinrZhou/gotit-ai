#!/usr/bin/env python3
"""Gate git commit / gh pr when code changed without doc/OpenSpec updates."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

CODE_PREFIXES = (
    "src/",
    "web/src/",
    "web/index.html",
    "web/vite.config.",
    "web/package.json",
    "tests/",
    "pyproject.toml",
    "skills/",
    "docker-compose.yml",
    "scripts/",
    "alembic/",
    "prompts/",
)

OPENSPEC_PREFIXES = (
    "openspec/",
    "docs/adr/",
    "docs/VISION.md",
    "docs/SYSTEM.md",
    "AGENTS.md",
)

README_PREFIXES = (
    "README.md",
    "README.zh-CN.md",
    "docs/SYSTEM.md",
)

COMMIT_RE = re.compile(r"\bgit\s+commit\b")
PR_RE = re.compile(r"\bgh\s+pr\s+(create|edit)\b")

ASK_OPENSPEC = (
    "Code changed without OpenSpec / SYSTEM updates. Sync `openspec/changes/` "
    "and/or `docs/SYSTEM.md` to match the work, then retry. "
    "Trivial-only edits may proceed after you confirm."
)

ASK_README = (
    "Product/user-facing code changed but README / docs/SYSTEM.md were not "
    "updated. Sync `docs/SYSTEM.md` (and README.md / README.zh-CN.md if the "
    "pitch or quick start drifted), then retry the commit/PR."
)

AGENT_OPENSPEC = (
    "Docs/OpenSpec gate: product/code files are dirty but openspec / "
    "docs/SYSTEM.md / VISION / AGENTS were not updated. Update artifacts, then "
    "retry. Skip only if the diff is truly trivial."
)

AGENT_README = (
    "README/SYSTEM gate: code that likely changes user-facing product story is "
    "dirty, but README.md / README.zh-CN.md / docs/SYSTEM.md were not touched. "
    "Update docs/SYSTEM.md first (agent onboarding snapshot), then README if "
    "humans need the same story. Retry commit/PR after."
)

# Paths that usually imply user-facing story / architecture drift
USER_FACING_PREFIXES = (
    "src/gotit/api/",
    "src/gotit/mcp/",
    "src/gotit/core/",
    "web/src/pages/",
    "web/src/components/Shell/",
    "web/src/components/ModeHeader/",
    "docs/VISION.md",
)


def _git_changed_files() -> list[str]:
    cmds = [
        ["git", "status", "--porcelain", "-uall"],
        ["git", "diff", "--name-only", "HEAD"],
        ["git", "diff", "--name-only", "--cached"],
    ]
    files: set[str] = set()
    for cmd in cmds:
        try:
            out = subprocess.check_output(
                cmd, cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            if cmd[1] == "status":
                path = line[3:].strip()
                if " -> " in path:
                    path = path.split(" -> ", 1)[1]
            else:
                path = line
            files.add(path.replace("\\", "/"))
    return sorted(files)


def _matches(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path == p or path.startswith(p) for p in prefixes)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        print(json.dumps({"permission": "allow"}))
        return

    command = payload.get("command") or ""
    if not (COMMIT_RE.search(command) or PR_RE.search(command)):
        print(json.dumps({"permission": "allow"}))
        return

    changed = _git_changed_files()
    code_changed = any(_matches(p, CODE_PREFIXES) for p in changed)
    openspec_touched = any(_matches(p, OPENSPEC_PREFIXES) for p in changed)
    readme_touched = any(_matches(p, README_PREFIXES) for p in changed)
    user_facing = any(_matches(p, USER_FACING_PREFIXES) for p in changed)

    if code_changed and not openspec_touched:
        print(
            json.dumps(
                {
                    "permission": "ask",
                    "user_message": ASK_OPENSPEC,
                    "agent_message": AGENT_OPENSPEC,
                }
            )
        )
        return

    if user_facing and not readme_touched:
        print(
            json.dumps(
                {
                    "permission": "ask",
                    "user_message": ASK_README,
                    "agent_message": AGENT_README,
                }
            )
        )
        return

    print(json.dumps({"permission": "allow"}))


if __name__ == "__main__":
    main()
