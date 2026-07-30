"""Workflow turns (examine / teach / drill) persist into companion thread messages."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_examine_turns_write_to_thread(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    day = "2026-07-30"
    r = await client.post(
        f"/v1/days/{day}/notes",
        headers=auth_headers,
        json={"body": "Attention is a weighted sum of values.", "title": "attn"},
    )
    assert r.status_code == 200
    note_id = r.json()["id"]

    r = await client.post(f"/v1/notes/{note_id}/ingest", headers=auth_headers)
    assert r.status_code == 200

    r = await client.post(
        "/v1/threads",
        headers=auth_headers,
        json={"title": "考我会话", "kind": "chat"},
    )
    assert r.status_code == 200
    thread_id = r.json()["id"]

    r = await client.post(
        "/v1/examine",
        headers=auth_headers,
        json={"note_id": note_id, "thread_id": thread_id},
    )
    assert r.status_code == 200
    follow = r.json()["verdict"]["follow_up"]
    assert follow

    r = await client.get(f"/v1/threads/{thread_id}/messages", headers=auth_headers)
    assert r.status_code == 200
    msgs = r.json()
    assert len(msgs) == 1
    assert msgs[0]["role"] == "agent"
    assert msgs[0]["agent_name"] == "axiom"
    assert msgs[0]["text"] == follow
    assert msgs[0]["metadata"]["workflow"] == "examine"
    assert msgs[0]["metadata"]["note_id"] == note_id

    r = await client.post(
        "/v1/examine",
        headers=auth_headers,
        json={
            "note_id": note_id,
            "thread_id": thread_id,
            "answer": "它是对 value 的加权求和",
            "history": [{"role": "examiner", "text": follow}],
        },
    )
    assert r.status_code == 200

    r = await client.get(f"/v1/threads/{thread_id}/messages", headers=auth_headers)
    msgs = r.json()
    assert len(msgs) >= 3
    assert msgs[1]["role"] == "user"
    assert msgs[1]["metadata"]["workflow"] == "examine"
    assert msgs[2]["role"] == "agent"
    assert msgs[2]["agent_name"] == "axiom"


@pytest.mark.asyncio
async def test_teach_turns_write_to_thread(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    r = await client.post(
        "/v1/threads",
        headers=auth_headers,
        json={"title": "回讲", "kind": "chat"},
    )
    thread_id = r.json()["id"]

    r = await client.post(
        "/v1/teach",
        headers=auth_headers,
        json={
            "topic": "注意力",
            "thread_id": thread_id,
            "you_taught_well": True,
        },
    )
    assert r.status_code == 200

    r = await client.get(f"/v1/threads/{thread_id}/messages", headers=auth_headers)
    msgs = r.json()
    assert len(msgs) == 1
    assert msgs[0]["agent_name"] == "echo"
    assert msgs[0]["metadata"]["workflow"] == "teach"
    assert "讲得清楚" in msgs[0]["text"]


@pytest.mark.asyncio
async def test_workflow_thread_ownership(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    missing = str(uuid4())
    r = await client.post(
        "/v1/teach",
        headers=auth_headers,
        json={
            "topic": "x",
            "thread_id": missing,
            "you_taught_well": False,
        },
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_examine_without_thread_unchanged(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    day = "2026-07-30"
    r = await client.post(
        f"/v1/days/{day}/notes",
        headers=auth_headers,
        json={"body": "Softmax normalizes scores.", "title": "sm"},
    )
    note_id = r.json()["id"]
    await client.post(f"/v1/notes/{note_id}/ingest", headers=auth_headers)

    r = await client.post(
        "/v1/examine",
        headers=auth_headers,
        json={"note_id": note_id},
    )
    assert r.status_code == 200
    assert r.json()["verdict"]["follow_up"]
