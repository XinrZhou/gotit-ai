from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from gotit.db.models import Base
from gotit.harness import Case, CaseResult, run_harness


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


@pytest.mark.asyncio
async def test_run_harness_writes_two_tables(session: AsyncSession) -> None:
    async def pass_runner() -> CaseResult:
        return CaseResult(passed=True, score=1.0, metrics={"latency_ms": 12})

    async def fail_runner() -> CaseResult:
        return CaseResult(passed=False, score=0.2, trace=[{"step": "x"}])

    cases = [
        Case(case_id="axiom-001", case_type="verdict", layer="agent", runner=pass_runner),
        Case(case_id="compass-002", case_type="extract", layer="agent", runner=fail_runner),
    ]
    run = await run_harness(session, cases, case_set="dev", label="baseline")

    assert run.case_set == "dev"
    assert run.summary == {"total": 2, "passed": 1, "failed": 1}
    assert run.verdict == "fail"

    from gotit.db import ops as day_ops

    results = await day_ops.list_harness_case_results(session, run_id=run.id)
    assert len(results) == 2
    by_case = {r.case_id: r for r in results}
    assert by_case["axiom-001"].passed is True
    assert by_case["compass-002"].passed is False
    assert by_case["compass-002"].trace == [{"step": "x"}]
