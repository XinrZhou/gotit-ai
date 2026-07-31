"""digest-to-claim: interest → promote → plan (reject / idempotent / strategy)."""

from __future__ import annotations

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from gotit.core.models import MasteryStatus
from gotit.db import ops as day_ops
from gotit.db.models import Base


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as sess:
        yield sess
        await sess.commit()
    await engine.dispose()


def test_claim_reject_vacuous() -> None:
    assert day_ops.claim_reject_reason("太棒了") is not None
    assert day_ops.claim_reject_reason("interesting") is not None
    assert day_ops.claim_reject_reason("短") is not None
    assert day_ops.claim_reject_reason("!!!") is not None
    ok = day_ops.claim_reject_reason(
        "Transformer 自注意力在序列长度 n 下的时间复杂度是 O(n²)"
    )
    assert ok is None


@pytest.mark.asyncio
async def test_promote_interest_plan_strategy(session: AsyncSession) -> None:
    """Pinned strategy: note stub + today's plan_items (ingest add_plan_item)."""
    day = date(2026, 7, 31)
    interest = await day_ops.record_interest(
        session,
        event_id="00000000-0000-0000-0000-000000000001",
        item_index=1,
        title="Redis Cluster 槽位迁移期间读请求可能短暂失败",
        link="https://example.com/redis",
        feed_id="qbitai",
        topic="redis",
    )
    result = await day_ops.promote_interest(
        session, interest.id, day=day
    )
    assert result.ok is True
    assert result.already_promoted is False
    assert result.note_id is not None
    assert len(result.claims) == 1
    assert len(result.plan_item_ids) == 1
    assert result.claims[0].status == MasteryStatus.NOT_YET

    plan = await day_ops.get_plan(session, day)
    claim_ids = {i.claim_id for i in plan.items if i.claim_id}
    assert result.claims[0].id in claim_ids

    today = await day_ops.get_today(session, day=day)
    assert any(i.claim_id == result.claims[0].id for i in today.plan.items)


@pytest.mark.asyncio
async def test_promote_reject_vacuous(session: AsyncSession) -> None:
    interest = await day_ops.record_interest(
        session,
        event_id="00000000-0000-0000-0000-000000000002",
        item_index=1,
        title="太棒了",
        feed_id="qbitai",
    )
    result = await day_ops.promote_interest(session, interest.id, day=date(2026, 7, 31))
    assert result.ok is False
    assert result.claims == []
    assert result.plan_item_ids == []
    assert result.reason
    assert result.rewrite_suggestion


@pytest.mark.asyncio
async def test_promote_idempotent(session: AsyncSession) -> None:
    day = date(2026, 7, 31)
    interest = await day_ops.record_interest(
        session,
        event_id="00000000-0000-0000-0000-000000000003",
        item_index=1,
        title="KV Cache 命中率下降会使 LLM 首 token 延迟显著上升",
        feed_id="hf-blog",
        topic="llm",
    )
    first = await day_ops.promote_interest(session, interest.id, day=day)
    assert first.ok is True
    second = await day_ops.promote_interest(session, interest.id, day=day)
    assert second.ok is True
    assert second.already_promoted is True
    assert [c.id for c in second.claims] == [c.id for c in first.claims]
    assert second.plan_item_ids == first.plan_item_ids

    plan = await day_ops.get_plan(session, day)
    matching = [i for i in plan.items if i.claim_id == first.claims[0].id]
    assert len(matching) == 1


@pytest.mark.asyncio
async def test_promote_rewrite_claim_texts(session: AsyncSession) -> None:
    interest = await day_ops.record_interest(
        session,
        event_id="00000000-0000-0000-0000-000000000004",
        item_index=1,
        title="有意思",
        feed_id="qbitai",
    )
    bad = await day_ops.promote_interest(session, interest.id, day=date(2026, 7, 31))
    assert bad.ok is False
    fixed = await day_ops.promote_interest(
        session,
        interest.id,
        day=date(2026, 7, 31),
        claim_texts=["PG 的 MVCC 在长事务下会导致表膨胀加剧"],
    )
    assert fixed.ok is True
    assert len(fixed.claims) == 1


@pytest.mark.asyncio
async def test_promote_rest_endpoint(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    ev = await client.post(
        "/v1/shell/events",
        headers=auth_headers,
        json={
            "job": "news",
            "items": [
                {
                    "n": 1,
                    "title": "Attention 掩码错误会导致 decoder 训练不稳定",
                    "link": "https://example.com/attn",
                    "feed_id": "openai-news",
                }
            ],
        },
    )
    assert ev.status_code == 200, ev.text
    event_id = ev.json()["id"]
    interest = await client.post(
        "/v1/shell/interest",
        headers=auth_headers,
        json={
            "event_id": event_id,
            "item_index": 1,
            "title": "Attention 掩码错误会导致 decoder 训练不稳定",
            "link": "https://example.com/attn",
            "feed_id": "openai-news",
            "topic": "transformers",
        },
    )
    assert interest.status_code == 200, interest.text
    iid = interest.json()["id"]

    promo = await client.post(
        f"/v1/shell/interests/{iid}/promote",
        headers=auth_headers,
        json={},
    )
    assert promo.status_code == 200, promo.text
    body = promo.json()
    assert body["ok"] is True
    assert len(body["claims"]) >= 1
    assert len(body["plan_item_ids"]) >= 1

    again = await client.post(
        f"/v1/shell/interests/{iid}/promote",
        headers=auth_headers,
        json={},
    )
    assert again.status_code == 200
    assert again.json()["already_promoted"] is True

    act = await client.get(
        "/v1/shell/activity?kinds=interest&limit=20", headers=auth_headers
    )
    assert act.status_code == 200
    row = next(r for r in act.json() if r["id"] == iid)
    assert row["content"].get("promoted_claim_ids")
