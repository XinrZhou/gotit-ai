"""Harness REST: run case sets + human adopt/observe/reject."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_run_dev_and_adopt(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    r = await client.post(
        "/v1/harness/runs",
        headers=auth_headers,
        json={"case_set": "dev", "label": "api-test"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    run = body["run"]
    assert run["case_set"] == "dev"
    assert run["verdict"] in {"pass", "fail"}
    assert run["summary"]["total"] >= 1
    assert len(body["cases"]) == run["summary"]["total"]
    for key in (
        "gate_consistent",
        "routing_ok",
        "no_spurious_write",
        "failure_hook_ok",
    ):
        assert key in run["summary"]
        assert isinstance(run["summary"][key], bool)

    run_id = run["id"]
    r = await client.patch(
        f"/v1/harness/runs/{run_id}",
        headers=auth_headers,
        json={"decision": "adopt", "note": "gate signals look good"},
    )
    assert r.status_code == 200, r.text
    decided = r.json()
    assert decided["summary"]["decision"] == "adopt"
    assert decided["summary"]["decision_note"] == "gate signals look good"
    assert decided["summary"].get("decided_at")
    assert decided["summary"].get("suite_version")

    r = await client.get("/v1/harness/runs?limit=5", headers=auth_headers)
    assert r.status_code == 200
    ids = [x["id"] for x in r.json()]
    assert run_id in ids

    r = await client.get(
        "/v1/harness/runs?decision=adopt&limit=10", headers=auth_headers
    )
    assert r.status_code == 200
    assert any(x["id"] == run_id for x in r.json())

    r = await client.get(f"/v1/harness/runs/{run_id}", headers=auth_headers)
    assert r.status_code == 200
    detail = r.json()
    assert detail["run"]["summary"]["decision"] == "adopt"
    assert len(detail["cases"]) >= 1


@pytest.mark.asyncio
async def test_decide_unknown_run_404(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    r = await client.patch(
        "/v1/harness/runs/00000000-0000-4000-8000-000000000099",
        headers=auth_headers,
        json={"decision": "reject"},
    )
    assert r.status_code == 404
