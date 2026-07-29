"""Mastery graph: fail events, confused_with, budget helpers."""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient

from gotit.core.mastery_graph import (
    CONFUSED_THRESHOLD,
    canonical_claim_pair,
    format_budget_block,
    pick_confused_neighbors,
)
from gotit.core.models import MasteryStatus
from gotit.db.models import ClaimRow
from gotit.db.ops import graph as graph_ops
from gotit.db.session import session_scope


def test_canonical_and_pick_neighbors() -> None:
    a = uuid4()
    b = uuid4()
    c = uuid4()
    src, tgt = canonical_claim_pair(a, b)
    assert str(src) <= str(tgt)
    edges = [
        (*canonical_claim_pair(a, b), CONFUSED_THRESHOLD),
        (*canonical_claim_pair(a, c), 1),
    ]
    picked = pick_confused_neighbors(target_id=a, edges=edges)
    assert b in picked
    assert c not in picked


def test_format_budget_block() -> None:
    assert format_budget_block(confused_labels=[], fail_reasons=[]) is None
    block = format_budget_block(
        confused_labels=["pointer vs array"],
        fail_reasons=["owe_next: mixed up free"],
    )
    assert block is not None
    assert "Easy to confuse" in block
    assert "pointer" in block


@pytest.mark.asyncio
async def test_fail_grows_confused_and_graph_obs(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    async with session_scope() as session:
        c1 = ClaimRow(
            id=uuid4(),
            user_id="local",
            text="Claim A about pointers",
            status=MasteryStatus.NOT_YET.value,
            topic="c-memory",
        )
        c2 = ClaimRow(
            id=uuid4(),
            user_id="local",
            text="Claim B about arrays",
            status=MasteryStatus.NOT_YET.value,
            topic="c-memory",
        )
        session.add_all([c1, c2])
        await session.flush()
        id1, id2 = c1.id, c2.id

        await graph_ops.record_verify_mastery_writeback(
            session,
            user_id="local",
            claim_id=id1,
            topic="c-memory",
            gate_verdict="owe_next",
            reason="missed free",
        )
        r2 = await graph_ops.record_verify_mastery_writeback(
            session,
            user_id="local",
            claim_id=id2,
            topic="c-memory",
            gate_verdict="almost",
            reason="almost",
        )
        assert r2["confused_edges_touched"] == 1
        await graph_ops.record_verify_mastery_writeback(
            session,
            user_id="local",
            claim_id=id1,
            topic="c-memory",
            gate_verdict="owe_next",
            reason="again",
        )
        budget = await graph_ops.build_budget_subgraph(
            session, user_id="local", claim_id=id1
        )
        assert id2 in budget.confused_claim_ids
        assert budget.prompt_block is not None

    graph = await client.get("/v1/obs/graph", headers=auth_headers)
    assert graph.status_code == 200
    body = graph.json()
    confused = [e for e in body["edges"] if e["rel"] == "confused_with"]
    assert len(confused) >= 1
    assert any(e.get("weight", 1) >= CONFUSED_THRESHOLD for e in confused)


@pytest.mark.asyncio
async def test_verify_writes_fail_event(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    async with session_scope() as session:
        claim = ClaimRow(
            id=uuid4(),
            user_id="local",
            text="Verify fail writes mastery",
            status=MasteryStatus.NOT_YET.value,
            topic="mg-test",
        )
        session.add(claim)
        await session.flush()
        claim_id = claim.id

    th = await client.post(
        "/v1/threads",
        headers=auth_headers,
        json={"kind": "chat"},
    )
    assert th.status_code == 200, th.text
    tid = th.json()["id"]

    res = await client.post(
        f"/v1/threads/{tid}/verify",
        headers=auth_headers,
        json={
            "claim_id": str(claim_id),
            "answer": "nope",
            "examine_verdict": "owe_next",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["gate"]["verdict"] == "owe_next"
    assert body["mastery_graph"]["fail_event"] is not None
