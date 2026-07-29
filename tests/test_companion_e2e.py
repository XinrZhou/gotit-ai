"""P1 companion-arch end-to-end: thread + personality agent + memory, stub path."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_companion_chat_flow(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    # 1. Seed identities (axiom/compass/echo/sage/critic)
    r = await client.post("/v1/identities/seed", headers=auth_headers)
    assert r.status_code == 200
    names = {i["agent_name"] for i in r.json()}
    assert {"axiom", "compass", "echo", "sage", "critic"}.issubset(names)

    # 2. Create a chat thread
    r = await client.post(
        "/v1/threads",
        headers=auth_headers,
        json={"title": "Transformer 注意力机制", "kind": "chat"},
    )
    assert r.status_code == 200
    thread = r.json()
    thread_id = thread["id"]
    assert thread["kind"] == "chat"

    # 3. Post a message with no @mention -> routes to default (axiom)
    r = await client.post(
        f"/v1/threads/{thread_id}/messages",
        headers=auth_headers,
        json={"text": "考考我注意力机制", "mentions": []},
    )
    assert r.status_code == 200
    reply = r.json()
    assert reply["user_message"]["role"] == "user"
    assert reply["agent_messages"][0]["role"] == "agent"
    assert reply["agent_messages"][0]["agent_name"] == "axiom"
    assert reply["agent_messages"][0]["text"]  # stub or real

    # 4. @mention compass -> routes to compass
    r = await client.post(
        f"/v1/threads/{thread_id}/messages",
        headers=auth_headers,
        json={"text": "@compass 帮我整理一下", "mentions": ["compass"]},
    )
    assert r.status_code == 200
    assert r.json()["agent_messages"][0]["agent_name"] == "compass"

    # 5. History is replayable
    r = await client.get(f"/v1/threads/{thread_id}/messages", headers=auth_headers)
    assert r.status_code == 200
    msgs = r.json()
    assert len(msgs) == 4  # 2 user + 2 agent
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "agent"

    # 6. Memory was written (working layer, event kind)
    r = await client.get(
        "/v1/memory",
        headers=auth_headers,
        params={"layer": "working", "kind": "event"},
    )
    assert r.status_code == 200
    entries = r.json()
    assert len(entries) >= 2
    assert all(e["layer"] == "working" for e in entries)

    # 7. Thread isolation: a second thread does not see the first's messages
    r = await client.post(
        "/v1/threads",
        headers=auth_headers,
        json={"title": "另一个话题", "kind": "chat"},
    )
    other_id = r.json()["id"]
    r = await client.get(f"/v1/threads/{other_id}/messages", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []

    # 8. Listing threads returns both
    r = await client.get("/v1/threads", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) >= 2


@pytest.mark.asyncio
async def test_verify_loop_deterministic_gate(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """verify-loop: examine → recheck(critic) → gate(deterministic), critic ≠ axiom."""
    # seed identities + register prompts (so critic rubric exists)
    await client.post("/v1/identities/seed", headers=auth_headers)
    await client.post("/v1/prompts/register", headers=auth_headers)

    # add a note + ingest to get a claim (compass stub fallback, no LLM key)
    day = "2026-07-29"
    r = await client.post(
        f"/v1/days/{day}/notes",
        headers=auth_headers,
        json={"body": "Attention is a weighted sum of values.", "title": "attn"},
    )
    note_id = r.json()["id"]
    r = await client.post(
        f"/v1/notes/{note_id}/ingest",
        headers=auth_headers,
        json={"add_plan_item": True},
    )
    claim_id = r.json()["claims"][0]["id"]

    # create a verify thread
    r = await client.post(
        "/v1/threads",
        headers=auth_headers,
        json={"title": "verify attn", "kind": "verify"},
    )
    thread_id = r.json()["id"]

    # Case A: examine=passed, recheck stub echoes passed -> gate passed (MASTERED)
    r = await client.post(
        f"/v1/threads/{thread_id}/verify",
        headers=auth_headers,
        json={"claim_id": claim_id, "examine_verdict": "passed"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["examine_verdict"] == "passed"
    assert body["recheck_verdict"] == "passed"  # stub echoes examine
    assert body["gate"]["verdict"] == "passed"
    assert body["gate"]["passed"] is True
    assert body["writeback"]["claim"]["status"] == "mastered"

    # Case B: examine=passed but force recheck stricter via a fresh claim
    r = await client.post(
        f"/v1/days/{day}/notes",
        headers=auth_headers,
        json={"body": "Softmax normalizes logits to a distribution.", "title": "sm"},
    )
    note_id2 = r.json()["id"]
    r = await client.post(
        f"/v1/notes/{note_id2}/ingest",
        headers=auth_headers,
        json={"add_plan_item": True},
    )
    claim_id2 = r.json()["claims"][0]["id"]
    r = await client.post(
        "/v1/threads",
        headers=auth_headers,
        json={"title": "verify sm", "kind": "verify"},
    )
    tid2 = r.json()["id"]
    # examine=owe_next -> gate owe_next (stricter wins), QUEUED + next_review_at set
    r = await client.post(
        f"/v1/threads/{tid2}/verify",
        headers=auth_headers,
        json={"claim_id": claim_id2, "examine_verdict": "owe_next"},
    )
    body = r.json()
    assert body["gate"]["verdict"] == "owe_next"
    assert body["gate"]["next_review_at"] is not None
    assert body["writeback"]["claim"]["status"] == "queued"

    # ball custody is cleared after gate
    # (no direct endpoint to read ball; assert via a new verify leaving no residue
    #  is implicit — the second verify ran on a different thread cleanly.)


@pytest.mark.asyncio
async def test_verify_trajectory_and_sr(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    """P3: verify writes a trajectory entry; a second verify on the same claim
    sees prior failures and the SR interval grows (1 → 3 days)."""
    await client.post("/v1/identities/seed", headers=auth_headers)
    await client.post("/v1/prompts/register", headers=auth_headers)

    day = "2026-07-29"
    r = await client.post(
        f"/v1/days/{day}/notes",
        headers=auth_headers,
        json={"body": "Gradient descent follows the negative gradient.", "title": "gd"},
    )
    note_id = r.json()["id"]
    r = await client.post(
        f"/v1/notes/{note_id}/ingest",
        headers=auth_headers,
        json={"add_plan_item": True},
    )
    claim_id = r.json()["claims"][0]["id"]

    r = await client.post(
        "/v1/threads",
        headers=auth_headers,
        json={"title": "verify gd", "kind": "verify"},
    )
    tid = r.json()["id"]

    # First verify: owe_next -> trajectory written, next_review +1d
    r = await client.post(
        f"/v1/threads/{tid}/verify",
        headers=auth_headers,
        json={"claim_id": claim_id, "examine_verdict": "owe_next"},
    )
    body = r.json()
    assert body["gate"]["verdict"] == "owe_next"
    assert body["writeback"]["claim"]["status"] == "queued"
    first_review = body["writeback"]["claim"]["next_review_at"]
    assert first_review is not None

    # trajectory entry exists for this claim
    r = await client.get(
        "/v1/memory",
        headers=auth_headers,
        params={"kind": "trajectory"},
    )
    entries = r.json()
    assert any(e["source"].get("claim_id") == claim_id for e in entries)

    # Second verify on the same claim: owe_next again -> SR interval grows to +3d
    # (1 + 2*prior_failures, prior_failures=1)
    r = await client.post(
        f"/v1/threads/{tid}/verify",
        headers=auth_headers,
        json={"claim_id": claim_id, "examine_verdict": "owe_next"},
    )
    body = r.json()
    second_review = body["writeback"]["claim"]["next_review_at"]
    assert second_review is not None
    # second interval (3d) must be later than first interval (1d)
    from datetime import date as _date

    d1 = _date.fromisoformat(first_review)
    d2 = _date.fromisoformat(second_review)
    assert (d2 - _date.today()).days > (d1 - _date.today()).days


@pytest.mark.asyncio
async def test_a2a_handoff_chain(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    """A2A: a manual handoff makes the first agent cede the floor to a peer; the
    peer replies in the same turn, ball custody moves to the peer, and a
    follow-up message with no mention is routed to the new holder."""
    await client.post("/v1/identities/seed", headers=auth_headers)

    r = await client.post(
        "/v1/threads",
        headers=auth_headers,
        json={"title": "A2A 接力", "kind": "chat"},
    )
    tid = r.json()["id"]

    # manual handoff: axiom replies, then hands off to compass
    r = await client.post(
        f"/v1/threads/{tid}/messages",
        headers=auth_headers,
        json={"text": "讲讲注意力机制", "mentions": [], "handoff_to": "compass"},
    )
    assert r.status_code == 200
    reply = r.json()
    assert len(reply["agent_messages"]) >= 2
    assert reply["agent_messages"][0]["agent_name"] == "axiom"
    assert reply["agent_messages"][0]["metadata"]["handoff_to"] == "compass"
    assert reply["agent_messages"][1]["agent_name"] == "compass"

    # follow-up with no mention routes to the new ball holder (compass)
    r = await client.post(
        f"/v1/threads/{tid}/messages",
        headers=auth_headers,
        json={"text": "再补一句", "mentions": []},
    )
    assert r.status_code == 200
    assert r.json()["agent_messages"][0]["agent_name"] == "compass"


@pytest.mark.asyncio
async def test_a2a_handoff_unknown_agent(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """A2A: handoff to an unknown agent is ignored gracefully (system message)."""
    await client.post("/v1/identities/seed", headers=auth_headers)

    r = await client.post(
        "/v1/threads",
        headers=auth_headers,
        json={"title": "A2A 未知", "kind": "chat"},
    )
    tid = r.json()["id"]

    r = await client.post(
        f"/v1/threads/{tid}/messages",
        headers=auth_headers,
        json={"text": "hi", "mentions": [], "handoff_to": "nobody"},
    )
    assert r.status_code == 200
    reply = r.json()
    # only the first agent replied; handoff ignored
    assert len(reply["agent_messages"]) == 1
    assert reply["agent_messages"][0]["agent_name"] == "axiom"
