"""Interview countdown ramp (P4) — tiers + nudges + prefs."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from gotit.core.interview_ramp import ramp_tier, suggest_action


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def test_ramp_tier_boundaries() -> None:
    assert ramp_tier(-1) == "past"
    assert ramp_tier(0) == "urgent"
    assert ramp_tier(24) == "urgent"
    assert ramp_tier(24.01) == "warm"
    assert ramp_tier(72) == "warm"
    assert ramp_tier(72.01) == "light"
    assert ramp_tier(168) == "light"
    assert ramp_tier(168.01) == "silent"


def test_suggest_action_quiet() -> None:
    s = suggest_action(round="tech_1", project_name="支付网关")
    assert "技术一面" in s
    assert "支付网关" in s
    assert "项目深挖" in s
    assert "加油" not in s


@pytest.mark.asyncio
async def test_upcoming_and_ramp_nudge_flow(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    now = datetime(2026, 7, 31, 8, 0, tzinfo=UTC)
    # warm: ~48h out
    scheduled = now + timedelta(hours=48)
    r = await client.post(
        "/v1/interviews",
        headers=auth_headers,
        json={
            "company": "Gamma",
            "role_title": "后端",
            "scheduled_at": _iso(scheduled),
            "round": "tech_2",
        },
    )
    assert r.status_code == 200
    iid = r.json()["id"]

    r = await client.get(
        f"/v1/interviews/upcoming?now={_iso(now)}",
        headers=auth_headers,
    )
    assert r.status_code == 200
    up = r.json()
    assert len(up) == 1
    assert up[0]["interview_id"] == iid
    assert up[0]["ramp_tier"] == "warm"
    assert "项目深挖" in up[0]["suggest_action"]

    r = await client.get(
        f"/v1/interviews/ramp-nudges?now={_iso(now)}",
        headers=auth_headers,
    )
    assert r.status_code == 200
    nudges = r.json()
    assert len(nudges) == 1
    assert nudges[0]["ramp_tier"] == "warm"

    r = await client.post(
        f"/v1/interviews/{iid}/ramp-nudged",
        headers=auth_headers,
        json={"at": _iso(now)},
    )
    assert r.status_code == 200
    assert r.json()["last_ramp_nudge_at"] is not None

    # Cooldown — no second nudge immediately
    r = await client.get(
        f"/v1/interviews/ramp-nudges?now={_iso(now + timedelta(hours=1))}",
        headers=auth_headers,
    )
    assert r.json() == []

    # Disable prefs
    r = await client.put(
        "/v1/interviews/ramp-prefs",
        headers=auth_headers,
        json={"enabled": False, "max_nudges_per_week": 2},
    )
    assert r.status_code == 200
    assert r.json()["enabled"] is False

    # Far enough for cooldown but prefs off
    later = now + timedelta(hours=40)
    r = await client.get(
        f"/v1/interviews/ramp-nudges?now={_iso(later)}",
        headers=auth_headers,
    )
    assert r.json() == []

    # Upcoming still readable when prefs off
    r = await client.get(
        f"/v1/interviews/upcoming?now={_iso(later)}",
        headers=auth_headers,
    )
    assert len(r.json()) == 1


@pytest.mark.asyncio
async def test_urgent_has_no_ramp_nudge(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    now = datetime(2026, 7, 31, 12, 0, tzinfo=UTC)
    scheduled = now + timedelta(hours=12)
    await client.post(
        "/v1/interviews",
        headers=auth_headers,
        json={
            "company": "Delta",
            "role_title": "SRE",
            "scheduled_at": _iso(scheduled),
        },
    )
    r = await client.get(
        f"/v1/interviews/upcoming?now={_iso(now)}",
        headers=auth_headers,
    )
    assert r.json()[0]["ramp_tier"] == "urgent"
    r = await client.get(
        f"/v1/interviews/ramp-nudges?now={_iso(now)}",
        headers=auth_headers,
    )
    assert r.json() == []
