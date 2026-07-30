from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from gotit.db.models import Base
from gotit.harness import run_harness
from gotit.harness.cases.gold import build_gold_cases, compare_rows_from_gate_pairs
from gotit.harness.gold_claims import GOLD_CLAIMS, GOLD_CONFUSE_PAIR, by_slug


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


def test_gold_claim_count_in_band() -> None:
    assert 5 <= len(GOLD_CLAIMS) <= 10
    by_slug(GOLD_CONFUSE_PAIR[0])
    by_slug(GOLD_CONFUSE_PAIR[1])


def test_compare_rows_match_expect() -> None:
    for row in compare_rows_from_gate_pairs():
        if row["expect"] == "retest conversion":
            continue
        assert row["gate"] == row["expect"], row


@pytest.mark.asyncio
async def test_gold_harness_passes(session: AsyncSession) -> None:
    run = await run_harness(
        session, build_gold_cases(session), case_set="gold", label="pytest"
    )
    assert run.verdict == "pass"
    assert run.summary == {"total": 3, "passed": 3, "failed": 0}
