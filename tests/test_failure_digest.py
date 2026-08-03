"""Failure digest queue: examine almost|owe_next → pending WeChat short message."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from gotit.core.models import MasteryStatus, PlanItemSource
from gotit.db.models import Base, ClaimRow, LearningDayRow, PlanItemRow
from gotit.db.ops import claim as claim_ops
from gotit.db.ops import memory as memory_ops


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as sess:
        yield sess
        await sess.commit()
    await engine.dispose()


async def _seed_claim(session: AsyncSession, *, text: str = "Attention core") -> UUID:
    claim_id = uuid4()
    day_id = uuid4()
    session.add(
        LearningDayRow(id=day_id, user_id="local", day=date(2026, 7, 30), timezone="UTC")
    )
    session.add(
        ClaimRow(
            id=claim_id,
            user_id="local",
            text=text,
            status=MasteryStatus.NOT_YET.value,
            topic="transformers",
        )
    )
    session.add(
        PlanItemRow(
            id=uuid4(),
            day_id=day_id,
            title="考 attention",
            source=PlanItemSource.MANUAL.value,
            status="planned",
            claim_id=claim_id,
        )
    )
    await session.flush()
    return claim_id


@pytest.mark.asyncio
async def test_failure_digest_once_per_claim_verdict(session: AsyncSession) -> None:
    claim_id = await _seed_claim(session)

    wb1 = await claim_ops.apply_examine_verdict(
        session, claim_id, verdict="owe_next", user_id="local"
    )
    assert wb1.get("failure_digest_id")
    pending = await memory_ops.list_pending_failure_digests(session, user_id="local")
    assert len(pending) == 1
    assert pending[0].content["verdict"] == "owe_next"

    wb2 = await claim_ops.apply_examine_verdict(
        session, claim_id, verdict="owe_next", user_id="local"
    )
    assert wb2.get("failure_digest_id") is None
    pending2 = await memory_ops.list_pending_failure_digests(session, user_id="local")
    assert len(pending2) == 1

    marked = await memory_ops.mark_failure_digest_notified(
        session, pending[0].id, user_id="local"
    )
    assert marked.content["notified"] is True
    assert await memory_ops.list_pending_failure_digests(session, user_id="local") == []


@pytest.mark.asyncio
async def test_passed_does_not_write_failure_digest(session: AsyncSession) -> None:
    claim_id = await _seed_claim(session, text="Already known")
    wb = await claim_ops.apply_examine_verdict(
        session, claim_id, verdict="passed", user_id="local"
    )
    assert wb.get("failure_digest_id") is None
    assert await memory_ops.list_pending_failure_digests(session, user_id="local") == []
    # Direct ops also refuse non-failure verdicts.
    assert (
        await memory_ops.maybe_record_failure_digest(
            session,
            user_id="local",
            claim_id=claim_id,
            claim_text="Already known",
            verdict="passed",
        )
        is None
    )


@pytest.mark.asyncio
async def test_failure_digest_upsert_fills_follow_up(session: AsyncSession) -> None:
    claim_id = await _seed_claim(session, text="Need tip")
    first = await memory_ops.maybe_record_failure_digest(
        session,
        user_id="local",
        claim_id=claim_id,
        claim_text="Need tip",
        verdict="almost",
    )
    assert first is not None
    assert first.content.get("follow_up") is None

    filled = await memory_ops.maybe_record_failure_digest(
        session,
        user_id="local",
        claim_id=claim_id,
        claim_text="Need tip",
        verdict="almost",
        follow_up="记得对比 softmax 与 argmax",
        reason="gate: almost",
    )
    assert filled is not None
    assert filled.content["follow_up"] == "记得对比 softmax 与 argmax"
    assert filled.content["reason"] == "gate: almost"
    assert filled.content.get("notified") is False

    again = await memory_ops.maybe_record_failure_digest(
        session,
        user_id="local",
        claim_id=claim_id,
        claim_text="Need tip",
        verdict="almost",
        follow_up="另一句",
    )
    assert again is None
    pending = await memory_ops.list_pending_failure_digests(session, user_id="local")
    assert len(pending) == 1
    assert pending[0].content["follow_up"] == "记得对比 softmax 与 argmax"


@pytest.mark.asyncio
async def test_almost_and_owe_next_digests_coexist(session: AsyncSession) -> None:
    claim_id = await _seed_claim(session, text="Partial then fail")
    wb_almost = await claim_ops.apply_examine_verdict(
        session, claim_id, verdict="almost", user_id="local"
    )
    assert wb_almost.get("failure_digest_id")
    wb_owe = await claim_ops.apply_examine_verdict(
        session, claim_id, verdict="owe_next", user_id="local"
    )
    assert wb_owe.get("failure_digest_id")
    pending = await memory_ops.list_pending_failure_digests(session, user_id="local")
    verdicts = {p.content["verdict"] for p in pending}
    assert verdicts == {"almost", "owe_next"}
    assert len(pending) == 2
