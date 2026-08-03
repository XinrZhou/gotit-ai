"""Replay + holdout harness contracts (no live LLM)."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from gotit.db.models import Base
from gotit.harness import SUITE_VERSION, run_harness
from gotit.harness.cases.holdout import build_holdout_cases
from gotit.harness.cases.replay import build_replay_cases


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
async def test_replay_cases_pass(session: AsyncSession) -> None:
    cases = build_replay_cases(session)
    assert len(cases) >= 8
    run = await run_harness(session, cases, case_set="replay", label="test-replay")
    assert run.verdict == "pass", run.summary
    assert run.summary.get("suite_version") == SUITE_VERSION


@pytest.mark.asyncio
async def test_holdout_cases_pass(session: AsyncSession) -> None:
    cases = build_holdout_cases(session)
    assert len(cases) >= 3
    run = await run_harness(session, cases, case_set="holdout", label="test-holdout")
    assert run.verdict == "pass", run.summary
    assert run.summary.get("suite_version") == SUITE_VERSION
    # Isolation: holdout case ids must not reuse gold-* prefixes.
    from gotit.db import ops as day_ops

    results = await day_ops.list_harness_case_results(session, run_id=run.id)
    assert all(not r.case_id.startswith("gold-") for r in results)


@pytest.mark.asyncio
async def test_adopt_binds_suite_version(session: AsyncSession) -> None:
    from gotit.db import ops as day_ops
    from gotit.harness import Case, CaseResult

    async def pass_runner() -> CaseResult:
        return CaseResult(passed=True)

    run = await run_harness(
        session,
        [Case(case_id="x", case_type="smoke", layer="system", runner=pass_runner)],
        case_set="dev",
        label="suite-pin",
    )
    assert run.summary.get("suite_version") == SUITE_VERSION

    decided = await day_ops.set_harness_decision(
        session, run.id, decision="adopt", note="pin check"
    )
    assert decided.summary["suite_version"] == SUITE_VERSION
    assert decided.summary["decision"] == "adopt"

    overridden = await day_ops.set_harness_decision(
        session,
        run.id,
        decision="observe",
        note="override pin",
        suite_version="custom.pin.1",
    )
    assert overridden.summary["suite_version"] == "custom.pin.1"
