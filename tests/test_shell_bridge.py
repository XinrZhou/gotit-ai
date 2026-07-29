"""OpenClaw bridge: shell_event / interest / profile / graph."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_shell_event_interest_activity_profile_graph(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    ev = await client.post(
        "/v1/shell/events",
        headers=auth_headers,
        json={
            "job": "morning",
            "items": [
                {
                    "n": 1,
                    "title": "Test headline",
                    "link": "https://example.com/a",
                    "feed_id": "solidot",
                    "label": "科技·Solidot",
                }
            ],
            "errors": ["少数派: timeout"],
            "skill": "digest",
            "channel": "openclaw-weixin",
        },
    )
    assert ev.status_code == 200, ev.text
    body = ev.json()
    assert body["kind"] == "shell_event"
    assert body["layer"] == "working"
    event_id = body["id"]
    assert body["content"]["items"][0]["title"] == "Test headline"

    interest = await client.post(
        "/v1/shell/interest",
        headers=auth_headers,
        json={
            "event_id": event_id,
            "item_index": 1,
            "title": "Test headline",
            "link": "https://example.com/a",
            "feed_id": "solidot",
            "topic": "tech-news",
        },
    )
    assert interest.status_code == 200, interest.text
    assert interest.json()["kind"] == "interest"
    assert interest.json()["layer"] == "long"

    # trajectory for profile weak topics
    mem = await client.post(
        "/v1/memory",
        headers=auth_headers,
        json={
            "layer": "long",
            "kind": "trajectory",
            "topic": "transformers",
            "content": {"verdict": "owe_next", "claim_id": "00000000-0000-0000-0000-000000000001"},
        },
    )
    assert mem.status_code == 200, mem.text

    act = await client.get("/v1/shell/activity?limit=20", headers=auth_headers)
    assert act.status_code == 200
    kinds = {row["kind"] for row in act.json()}
    assert "shell_event" in kinds
    assert "interest" in kinds

    profile = await client.get("/v1/obs/profile", headers=auth_headers)
    assert profile.status_code == 200
    p = profile.json()
    assert p["shell_event_total"] >= 1
    assert p["interest_total"] >= 1
    assert p["trajectory_total"] >= 1
    assert "transformers" in p["weak_topics"]

    # seed a claim for graph (RSS must NOT become claim nodes)
    ing = await client.post(
        "/v1/ingest",
        headers=auth_headers,
        json={"material": "Attention is all you need for graph bridge."},
    )
    assert ing.status_code == 200, ing.text

    graph = await client.get("/v1/obs/graph", headers=auth_headers)
    assert graph.status_code == 200
    g = graph.json()
    assert "nodes" in g and "edges" in g
    types = {n["type"] for n in g["nodes"]}
    assert "interest" in types
    assert "claim" in types
    rels = {e["rel"] for e in g["edges"]}
    assert "interest_topic" in rels
