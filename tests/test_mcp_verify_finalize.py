"""MCP examine / verify share Critic + gate finalize with REST."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_mcp_examine_direct_verdict_runs_gate_path(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """gotit_examine(verdict=) must not bypass Critic + deterministic gate."""
    day = "2026-07-31"
    r = await client.post(
        f"/v1/days/{day}/notes",
        headers=auth_headers,
        json={"body": "Mastery is gated in code.", "title": "gate"},
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

    from gotit.mcp.server import gotit_examine

    body = await gotit_examine(claim_id=claim_id, verdict="almost")
    assert "error" not in body
    assert body["writeback"]["claim"]["status"] == "in_progress"
    assert body["verify"]["examine_verdict"] == "almost"
    assert body["verify"]["recheck_verdict"] == "almost"
    assert body["verify"]["gate_verdict"] == "almost"
    assert body["verdict"]["verdict"] == "almost"


@pytest.mark.asyncio
async def test_mcp_start_verify_uses_shared_finalize(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    day = "2026-07-31"
    r = await client.post(
        f"/v1/days/{day}/notes",
        headers=auth_headers,
        json={"body": "Thread verify shares finalize.", "title": "tv"},
    )
    note_id = r.json()["id"]
    r = await client.post(
        f"/v1/notes/{note_id}/ingest",
        headers=auth_headers,
        json={"add_plan_item": True},
    )
    claim_id = r.json()["claims"][0]["id"]

    r = await client.post("/v1/threads", headers=auth_headers, json={})
    assert r.status_code == 200
    thread_id = r.json()["id"]

    from gotit.mcp.server import gotit_start_verify

    body = await gotit_start_verify(
        thread_id=thread_id, claim_id=claim_id, examine_verdict="owe_next"
    )
    assert "error" not in body
    assert body["examine_verdict"] == "owe_next"
    assert body["recheck_verdict"] == "owe_next"
    assert body["gate"]["verdict"] == "owe_next"
    assert body["writeback"]["claim"]["status"] == "queued"
    assert "mastery_graph" in body
