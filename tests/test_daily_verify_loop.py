"""Daily verify loop: examine finalize shares Critic + gate with thread verify."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_examine_direct_verdict_runs_gate_path(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    day = "2026-07-30"
    r = await client.post(
        f"/v1/days/{day}/notes",
        headers=auth_headers,
        json={"body": "Attention is a weighted sum.", "title": "attn"},
    )
    assert r.status_code == 200
    note_id = r.json()["id"]
    r = await client.post(
        f"/v1/notes/{note_id}/ingest",
        headers=auth_headers,
        json={"add_plan_item": True},
    )
    assert r.status_code == 200
    claim_id = r.json()["claims"][0]["id"]

    r = await client.post(
        "/v1/examine",
        headers=auth_headers,
        json={"claim_id": claim_id, "verdict": "almost"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["writeback"]["claim"]["status"] == "in_progress"
    assert body["verify"]["examine_verdict"] == "almost"
    assert body["verify"]["recheck_verdict"] == "almost"
    assert body["verify"]["gate_verdict"] == "almost"
    assert body["verdict"]["verdict"] == "almost"


@pytest.mark.asyncio
async def test_today_due_claims_surface(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    day = "2026-07-30"
    r = await client.post(
        f"/v1/days/{day}/notes",
        headers=auth_headers,
        json={"body": "Context on a budget.", "title": "P4"},
    )
    note_id = r.json()["id"]
    r = await client.post(
        f"/v1/notes/{note_id}/ingest",
        headers=auth_headers,
        json={"add_plan_item": True},
    )
    claim_id = r.json()["claims"][0]["id"]
    await client.post(
        "/v1/examine",
        headers=auth_headers,
        json={"claim_id": claim_id, "verdict": "almost"},
    )

    r = await client.get("/v1/today", headers=auth_headers, params={"day": day})
    assert r.status_code == 200
    due = r.json()["due_claims"]
    assert any(c["id"] == claim_id for c in due)
    assert any(i.get("claim_id") == claim_id for i in r.json()["plan"]["items"])
