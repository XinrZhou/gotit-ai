"""Best-effort Apple Calendar sync for interviews (not in gotit.core)."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from uuid import UUID

from gotit.core.models import InterviewEventView

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "skills" / "apple-interview" / "sync_interview.py"


def _run(argv: list[str], *, timeout_s: float = 90.0) -> str | None:
    if not _SCRIPT.is_file():
        return f"apple-interview missing: {_SCRIPT}"
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
                str(_SCRIPT),
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
    return err[-500:] or f"apple-interview exit {proc.returncode}"


def _title(company: str, role_title: str, round_name: str | None) -> str:
    base = f"{company.strip()} · {role_title.strip()}"
    if round_name and round_name.strip():
        return f"{base} · {round_name.strip()}"
    return base


def upsert_interview(
    *,
    interview_id: UUID | str,
    company: str,
    role_title: str,
    scheduled_at: datetime,
    round: str | None = None,
    notes: str | None = None,
    remind_offsets_hours: Sequence[int] | None = None,
    status: str = "scheduled",
) -> str | None:
    """Push interview → Calendar. Removes event when status is done/cancelled."""
    st = (status or "scheduled").lower()
    if st in {"done", "cancelled"}:
        return rm_interview(interview_id)

    alarms_raw = (
        list(remind_offsets_hours)
        if remind_offsets_hours is not None
        else [-24, -2]
    )
    # DB offsets are hours relative to start (negative = before). Calendar wants
    # positive hours-before.
    alarms = [abs(int(h)) for h in alarms_raw if int(h) != 0]
    alarm_arg = ",".join(str(h) for h in alarms) if alarms else "24,2"
    start = scheduled_at
    start_s = (
        start.isoformat() + "+00:00" if start.tzinfo is None else start.isoformat()
    )
    args = [
        "upsert",
        "--id",
        str(interview_id),
        "--title",
        _title(company, role_title, round),
        "--start",
        start_s,
        "--alarms",
        alarm_arg,
    ]
    if notes and notes.strip():
        args.extend(["--notes", notes.strip()])
    return _run(args)


def rm_interview(interview_id: UUID | str) -> str | None:
    """Delete Calendar event tagged with this interview id."""
    return _run(["rm", "--id", str(interview_id)])


def sync_interview_to_calendar(view: InterviewEventView) -> str | None:
    """Best-effort Calendar upsert/rm from a persisted interview view."""
    return upsert_interview(
        interview_id=view.id,
        company=view.company,
        role_title=view.role_title,
        scheduled_at=view.scheduled_at,
        round=view.round,
        notes=view.notes,
        remind_offsets_hours=view.remind_offsets_hours,
        status=view.status.value,
    )
