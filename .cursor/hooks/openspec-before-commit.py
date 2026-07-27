#!/usr/bin/env python3
"""Gate git commit / gh pr when code changed without OpenSpec updates."""

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
)

OPENSPEC_PREFIXES = (
    "openspec/",
    "docs/adr/",
    "docs/VISION.md",
    "AGENTS.md",
)

COMMIT_RE = re.compile(r"\bgit\s+commit\b")
PR_RE = re.compile(r"\bgh\s+pr\s+(create|edit)\b")

ASK_MESSAGE = (
    "Code changed without OpenSpec updates. Sync `openspec/changes/` "
    "(or archive) to match the work, then retry the commit/PR. "
    "Trivial-only edits may proceed after you confirm."
)

AGENT_MESSAGE = (
    "OpenSpec gate: product/code files are dirty but openspec/ADR/VISION/AGENTS "
    "were not updated in the working tree. Update OpenSpec artifacts to match "
    "the intended change, then retry git commit / gh pr. Skip only if the diff "
    "is truly trivial (typo/comment/tiny docs)."
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

    if code_changed and not openspec_touched:
        print(
            json.dumps(
                {
                    "permission": "ask",
                    "user_message": ASK_MESSAGE,
                    "agent_message": AGENT_MESSAGE,
                }
            )
        )
        return

    print(json.dumps({"permission": "allow"}))


if __name__ == "__main__":
    main()
