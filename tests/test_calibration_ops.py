"""Cold-start calibration ops: writeback, due, confuse seed, synthetic."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from gotit.core.models import MasteryStatus
from gotit.db import ops as day_ops
from gotit.db.models import Base, ClaimRow, FailEventRow, GraphEdgeRow
from gotit.db.ops.graph import list_confused_edges


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


async def _seed_pool(session: AsyncSession, user_id: str = "local") -> list[ClaimRow]:
    rows: list[ClaimRow] = []
    specs = [
        ("redis A", "redis", 2, 1.5),
        ("redis B", "redis", 3, 2.0),
        ("redis C", "redis", 4, 1.2),
        ("sql A", "sql", 2, 1.5),
        ("sql B", "sql", 3, 2.0),
        ("sql C", "sql", 5, 1.8),
        ("http A", "http", 3, 1.5),
        ("http B", "http", 4, 1.5),
    ]
    for text, topic, diff, disc in specs:
        row = ClaimRow(
            id=uuid4(),
            user_id=user_id,
            text=text,
            status=MasteryStatus.NOT_YET.value,
            topic=topic,
            next_review_at=None,
            calibration={
                "difficulty": diff,
                "discrimination": disc,
                "knowledge_key": topic,
            },
        )
        session.add(row)
        rows.append(row)
    await session.flush()
    return rows


@pytest.mark.asyncio
async def test_calibration_incorrect_writeback_due_and_confuse(
    session: AsyncSession,
) -> None:
    today = date(2026, 7, 30)
    pool = await _seed_pool(session)
    ids = [c.id for c in pool]
    view = await day_ops.start_calibration(
        session, claim_ids=ids, as_of=today
    )
    assert view.current_item is not None
    assert not view.done

    first = view.current_item.claim_id
    view = await day_ops.answer_calibration(
        session,
        view.id,
        claim_id=first,
        outcome="incorrect",
        as_of=today,
    )
    claim = await session.get(ClaimRow, first)
    assert claim is not None
    assert claim.status == MasteryStatus.IN_PROGRESS.value
    assert claim.next_review_at == today

    fails = list(
        (
            await session.execute(
                select(FailEventRow).where(FailEventRow.claim_id == first)
            )
        )
        .scalars()
        .all()
    )
    assert len(fails) == 1
    assert fails[0].reason == "calibration"

    edges = await list_confused_edges(session, user_id="local", min_weight=1)
    assert any(
        e.source_claim_id == first or e.target_claim_id == first for e in edges
    )


@pytest.mark.asyncio
async def test_calibration_correct_clears_due(session: AsyncSession) -> None:
    today = date(2026, 7, 30)
    pool = await _seed_pool(session)
    view = await day_ops.start_calibration(
        session, claim_ids=[c.id for c in pool], as_of=today
    )
    assert view.current_item is not None
    cid = view.current_item.claim_id
    view = await day_ops.answer_calibration(
        session, view.id, claim_id=cid, outcome="correct", as_of=today
    )
    claim = await session.get(ClaimRow, cid)
    assert claim is not None
    assert claim.status == MasteryStatus.MASTERED.value
    assert claim.next_review_at is None


@pytest.mark.asyncio
async def test_calibration_finish_has_due_when_failures(
    session: AsyncSession,
) -> None:
    today = date(2026, 7, 30)
    pool = await _seed_pool(session)
    result = await day_ops.run_synthetic_calibration(
        session,
        true_theta=1.5,
        claim_ids=[c.id for c in pool],
        mode="deterministic",
        as_of=today,
    )
    assert result.item_count >= 1
    assert result.stop_reason is not None
    due = await day_ops.list_due_claims(session, today, user_id="local")
    assert len(due) >= 1
    assert result.theta_hat < 3.0


@pytest.mark.asyncio
async def test_synthetic_high_theta_direction(session: AsyncSession) -> None:
    today = date(2026, 7, 30)
    pool = await _seed_pool(session, user_id="synth-hi")
    result = await day_ops.run_synthetic_calibration(
        session,
        true_theta=5.0,
        claim_ids=[c.id for c in pool],
        user_id="synth-hi",
        mode="deterministic",
        as_of=today,
    )
    assert result.theta_hat > 3.0
    assert result.abs_error < 2.5


@pytest.mark.asyncio
async def test_seed_confused_without_peer_fail(session: AsyncSession) -> None:
    a = ClaimRow(
        id=uuid4(),
        user_id="local",
        text="a",
        topic="t",
        status=MasteryStatus.NOT_YET.value,
    )
    b = ClaimRow(
        id=uuid4(),
        user_id="local",
        text="b",
        topic="t",
        status=MasteryStatus.NOT_YET.value,
    )
    session.add_all([a, b])
    await session.flush()
    n = await day_ops.seed_confused_for_calibration(
        session,
        user_id="local",
        failed_claim_id=a.id,
        topic="t",
        pool_claim_ids=[a.id, b.id],
        limit=2,
    )
    assert n == 1
    edges = await list_confused_edges(session, user_id="local")
    assert len(edges) == 1
    # Everyday grow still requires peer fails — no automatic second path here.
    assert isinstance(edges[0], GraphEdgeRow)
