"""Best-effort Apple Reminders sync via skills/apple-plan (not in gotit.core)."""

from __future__ import annotations

import os
import subprocess
from datetime import date
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_IMPORT_SCRIPT = _REPO_ROOT / "skills" / "apple-plan" / "import_plan.py"


def _run(argv: list[str], *, timeout_s: float = 90.0) -> str | None:
    """Return error text or None on success. Skips when script missing."""
    if not _IMPORT_SCRIPT.is_file():
        return f"apple-plan missing: {_IMPORT_SCRIPT}"
    if os.environ.get("GOTIT_SKIP_APPLE_SYNC", "").strip() in {"1", "true", "yes"}:
        return None
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return None
    try:
        proc = subprocess.run(
            [
                "uv",
                "run",
                "--directory",
                str(_REPO_ROOT),
                "python",
                str(_IMPORT_SCRIPT),
                *argv,
            ],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return str(exc)
    if proc.returncode == 0:
        return None
    err = (proc.stderr or proc.stdout or "").strip()
    return err[-500:] or f"apple-plan exit {proc.returncode}"


def push_day(
    day: date,
    *,
    title: str | None = None,
    time: str | None = None,
    reconcile: bool = True,
) -> str | None:
    """Push gotit plan → Reminders for ``day`` (dueDate only, no alerts)."""
    args = ["push", "--day", day.isoformat(), "--apply"]
    # Reconcile only for full-day sync — single-title push must not wipe siblings.
    if reconcile and not title:
        args.append("--reconcile")
    if title:
        args.extend(["--title", title])
    if time:
        args.extend(["--time", time])
    return _run(args)


def rm_item(day: date, title: str) -> str | None:
    """Delete gotit-matching reminder (and gotit row if still present — prefer delete ops first)."""
    return _run(
        ["rm", "--day", day.isoformat(), "--title", title, "--apply"]
    )


def import_reminders(*, apply: bool = True) -> str | None:
    """Reminders → gotit (skip existing titles)."""
    args = ["reminders", "--list", "学习计划"]
    if apply:
        args.append("--apply")
    return _run(args, timeout_s=120.0)
