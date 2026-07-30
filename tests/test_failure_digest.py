"""Failure digest queue: examine almost|owe_next → pending WeChat short message."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from uuid import uuid4

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


@pytest.mark.asyncio
async def test_failure_digest_once_per_claim_verdict(session: AsyncSession) -> None:
    claim_id = uuid4()
    day_id = uuid4()
    session.add(
        LearningDayRow(id=day_id, user_id="local", day=date(2026, 7, 30), timezone="UTC")
    )
    session.add(
        ClaimRow(
            id=claim_id,
            user_id="local",
            text="Attention is all you need 的核心是什么",
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
