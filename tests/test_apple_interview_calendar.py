"""Apple Calendar bridge for interviews — skip under pytest."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from gotit.bridge.calendar import rm_interview, upsert_interview
from gotit.core.models import InterviewEventView, InterviewStatus


def test_calendar_bridge_skips_under_pytest() -> None:
    err = upsert_interview(
        interview_id=uuid4(),
        company="Acme",
        role_title="Backend",
        scheduled_at=datetime(2026, 8, 10, 6, 0, tzinfo=UTC),
        remind_offsets_hours=[-24, -2],
        status="scheduled",
    )
    assert err is None
    assert rm_interview(uuid4()) is None


def test_sync_view_done_uses_rm_path() -> None:
    from gotit.bridge.calendar import sync_interview_to_calendar

    view = InterviewEventView(
        id=uuid4(),
        user_id="default",
        company="Acme",
        role_title="Backend",
        scheduled_at=datetime(2026, 8, 10, 6, 0, tzinfo=UTC),
        round=None,
        status=InterviewStatus.DONE,
        notes=None,
        remind_offsets_hours=[-24, -2],
        last_reminded_at=None,
        last_ramp_nudge_at=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    assert sync_interview_to_calendar(view) is None
