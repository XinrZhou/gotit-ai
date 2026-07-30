"""Tests for scheduled real-world interview events (companion-os P3d)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


@pytest.mark.asyncio
async def test_interview_crud_and_status(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    scheduled = datetime(2026, 8, 1, 14, 0, tzinfo=UTC)
    r = await client.post(
        "/v1/interviews",
        headers=auth_headers,
        json={
            "company": "Acme",
            "role_title": "后端工程师",
            "scheduled_at": _iso(scheduled),
            "round": "tech_1",
            "notes": "线上",
        },
    )
    assert r.status_code == 200
    created = r.json()
    iid = created["id"]
    assert created["company"] == "Acme"
    assert created["status"] == "scheduled"
    assert created["remind_offsets_hours"] == [-24, -2]

    r = await client.get("/v1/interviews", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = await client.patch(
        f"/v1/interviews/{iid}",
        headers=auth_headers,
        json={"status": "done"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "done"

    r = await client.get("/v1/interviews", headers=auth_headers)
    assert r.json() == []

    r = await client.get("/v1/interviews?include_done=true", headers=auth_headers)
    assert len(r.json()) == 1

    r = await client.delete(f"/v1/interviews/{iid}", headers=auth_headers)
    assert r.status_code == 200
    r = await client.get("/v1/interviews?include_done=true", headers=auth_headers)
    assert r.json() == []


@pytest.mark.asyncio
async def test_due_reminders_offsets_and_dedup(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    scheduled = datetime(2026, 8, 10, 10, 0, tzinfo=UTC)
    r = await client.post(
        "/v1/interviews",
        headers=auth_headers,
        json={
            "company": "Beta",
            "role_title": "架构师",
            "scheduled_at": _iso(scheduled),
            "remind_offsets_hours": [-24, -2],
        },
    )
    iid = r.json()["id"]

    # Too early — no reminders
    early = scheduled + timedelta(hours=-25)
    r = await client.get(
        f"/v1/interviews/due-reminders?now={_iso(early)}",
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json() == []

    # -24h offset fires at scheduled - 24h
    fire_24 = scheduled + timedelta(hours=-24)
    r = await client.get(
        f"/v1/interviews/due-reminders?now={_iso(fire_24)}",
        headers=auth_headers,
    )
    due = r.json()
    assert len(due) == 1
    assert due[0]["offset_hours"] == -24
    assert due[0]["interview_id"] == iid

    # Still due before mark
    r = await client.get(
        f"/v1/interviews/due-reminders?now={_iso(fire_24 + timedelta(minutes=30))}",
        headers=auth_headers,
    )
    assert len(r.json()) == 1

    # Mark reminded — -24 offset deduped
    r = await client.post(
        f"/v1/interviews/{iid}/reminded",
        headers=auth_headers,
        json={"at": _iso(fire_24 + timedelta(minutes=5))},
    )
    assert r.status_code == 200

    r = await client.get(
        f"/v1/interviews/due-reminders?now={_iso(fire_24 + timedelta(hours=1))}",
        headers=auth_headers,
    )
    assert r.json() == []

    # -2h offset fires later
    fire_2 = scheduled + timedelta(hours=-2)
    r = await client.get(
        f"/v1/interviews/due-reminders?now={_iso(fire_2)}",
        headers=auth_headers,
    )
    due = r.json()
    assert len(due) == 1
    assert due[0]["offset_hours"] == -2

    # Stale window: 6h past fire time → drop
    stale = fire_2 + timedelta(hours=7)
    r = await client.get(
        f"/v1/interviews/due-reminders?now={_iso(stale)}",
        headers=auth_headers,
    )
    assert r.json() == []


@pytest.mark.asyncio
async def test_due_reminders_skip_non_scheduled(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    scheduled = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
    r = await client.post(
        "/v1/interviews",
        headers=auth_headers,
        json={
            "company": "Gamma",
            "role_title": "SRE",
            "scheduled_at": _iso(scheduled),
        },
    )
    iid = r.json()["id"]
    await client.patch(
        f"/v1/interviews/{iid}",
        headers=auth_headers,
        json={"status": "cancelled"},
    )
    fire = scheduled + timedelta(hours=-2)
    r = await client.get(
        f"/v1/interviews/due-reminders?now={_iso(fire)}",
        headers=auth_headers,
    )
    assert r.json() == []
