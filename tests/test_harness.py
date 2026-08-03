from __future__ import annotations

import ast
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from gotit.db.models import Base
from gotit.harness import (
    CONTRACT_ROLLUP_KEYS,
    Case,
    CaseResult,
    aggregate_run_summary,
    run_harness,
)
from gotit.harness.cases.dev import build_dev_cases


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
    assert run.summary["total"] == 2
    assert run.summary["passed"] == 1
    assert run.summary["failed"] == 1
    for key in CONTRACT_ROLLUP_KEYS:
        assert key in run.summary
        assert run.summary[key] is True  # vacuous: no tagged cases
    assert run.verdict == "fail"

    from gotit.db import ops as day_ops

    results = await day_ops.list_harness_case_results(session, run_id=run.id)
    assert len(results) == 2
    by_case = {r.case_id: r for r in results}
    assert by_case["axiom-001"].passed is True
    assert by_case["compass-002"].passed is False
    assert by_case["compass-002"].trace == [{"step": "x"}]


def test_aggregate_run_summary_contract_keys() -> None:
    """Nail stable summary key names for CLI / REST / docs."""
    assert CONTRACT_ROLLUP_KEYS == (
        "gate_consistent",
        "routing_ok",
        "no_spurious_write",
        "failure_hook_ok",
    )
    summary = aggregate_run_summary(
        [
            {
                "case_id": "gate-no-llm",
                "case_type": "deterministic_gate",
                "passed": True,
                "metrics": {"rollup": "gate_consistent"},
            },
            {
                "case_id": "check-routing",
                "case_type": "check_routing",
                "passed": True,
                "metrics": {"rollup": "routing_ok"},
            },
            {
                "case_id": "stub-no-spurious-write",
                "case_type": "stub_write",
                "passed": False,
                "metrics": {"rollup": "no_spurious_write"},
            },
            {
                "case_id": "failure-hook",
                "case_type": "failure_hook",
                "passed": True,
                "metrics": {"rollup": "failure_hook_ok"},
            },
            {
                "case_id": "other",
                "case_type": "smoke",
                "passed": True,
                "metrics": {},
            },
        ]
    )
    assert summary["total"] == 5
    assert summary["passed"] == 4
    assert summary["failed"] == 1
    assert summary["gate_consistent"] is True
    assert summary["routing_ok"] is True
    assert summary["no_spurious_write"] is False
    assert summary["failure_hook_ok"] is True


@pytest.mark.asyncio
async def test_dev_cases_roll_contract_metrics(session: AsyncSession) -> None:
    cases = build_dev_cases(session)
    run = await run_harness(session, cases, case_set="dev", label="contract")
    assert run.verdict == "pass", run.summary
    for key in CONTRACT_ROLLUP_KEYS:
        assert run.summary[key] is True, (key, run.summary)

    from gotit.db import ops as day_ops

    results = await day_ops.list_harness_case_results(session, run_id=run.id)
    by_id = {r.case_id: r for r in results}
    assert by_id["gate-no-llm"].metrics.get("rollup") == "gate_consistent"
    assert by_id["check-routing"].metrics.get("rollup") == "routing_ok"
    assert by_id["stub-no-spurious-write"].metrics.get("rollup") == "no_spurious_write"
    assert by_id["failure-hook"].metrics.get("rollup") == "failure_hook_ok"


@pytest.mark.asyncio
async def test_set_harness_decision_is_audit_only(session: AsyncSession) -> None:
    """adopt|observe|reject only writes summary — no prompt/skill side effects."""
    from sqlalchemy import func, select

    from gotit.db import ops as day_ops
    from gotit.db.models import PromptVersionRow, UserSkillRow

    async def pass_runner() -> CaseResult:
        return CaseResult(passed=True)

    run = await run_harness(
        session,
        [Case(case_id="x", case_type="smoke", layer="system", runner=pass_runner)],
        case_set="dev",
        label="decision-audit",
    )
    prompts_before = (
        await session.execute(select(func.count()).select_from(PromptVersionRow))
    ).scalar_one()
    skills_before = (
        await session.execute(select(func.count()).select_from(UserSkillRow))
    ).scalar_one()

    decided = await day_ops.set_harness_decision(
        session, run.id, decision="adopt", note="looks good"
    )
    assert decided.summary["decision"] == "adopt"
    assert decided.summary["decision_note"] == "looks good"
    assert decided.summary.get("decided_at")
    assert decided.summary.get("suite_version")

    prompts_after = (
        await session.execute(select(func.count()).select_from(PromptVersionRow))
    ).scalar_one()
    skills_after = (
        await session.execute(select(func.count()).select_from(UserSkillRow))
    ).scalar_one()
    assert prompts_after == prompts_before
    assert skills_after == skills_before

    # Filter by decision (optional list API).
    adopted = await day_ops.list_harness_runs(session, decision="adopt", limit=10)
    assert any(r.id == run.id for r in adopted)
    rejected = await day_ops.list_harness_runs(session, decision="reject", limit=10)
    assert all(r.id != run.id for r in rejected)


def test_harness_route_decide_has_no_prompt_skill_calls() -> None:
    """Static guard: PATCH decide path only calls set_harness_decision."""
    src = Path("src/gotit/api/routes/harness.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    decide_fn = None
    for node in tree.body:
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "decide_run":
            decide_fn = node
            break
    assert decide_fn is not None
    called: set[str] = set()
    for n in ast.walk(decide_fn):
        if isinstance(n, ast.Call):
            func = n.func
            if isinstance(func, ast.Attribute):
                called.add(func.attr)
            elif isinstance(func, ast.Name):
                called.add(func.id)
    assert "set_harness_decision" in called
    assert "register_prompts" not in called
    assert "install_skill" not in called
