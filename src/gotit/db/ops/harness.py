"""Harness run and case-result persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gotit.core.models import HarnessCaseResult, HarnessRun
from gotit.db.models import HarnessCaseResultRow, HarnessRunRow


def _harness_run_view(row: HarnessRunRow) -> HarnessRun:
    return HarnessRun(
        id=row.id,
        started_at=row.started_at or datetime.now(UTC),
        git_sha=row.git_sha,
        prompt_versions=dict(row.prompt_versions or {}),
        label=row.label,
        case_set=row.case_set,
        summary=dict(row.summary or {}),
        verdict=row.verdict,
        created_at=row.created_at or datetime.now(UTC),
    )


def _harness_case_view(row: HarnessCaseResultRow) -> HarnessCaseResult:
    return HarnessCaseResult(
        id=row.id,
        run_id=row.run_id,
        case_id=row.case_id,
        case_type=row.case_type,
        layer=row.layer,
        passed=bool(row.passed),
        score=row.score,
        metrics=dict(row.metrics or {}),
        trace=list(row.trace or []),
        created_at=row.created_at or datetime.now(UTC),
    )


async def add_harness_run(
    session: AsyncSession,
    *,
    started_at: datetime,
    case_set: str,
    label: str | None = None,
    git_sha: str | None = None,
    prompt_versions: dict[str, str] | None = None,
) -> HarnessRun:
    row = HarnessRunRow(
        id=uuid4(),
        started_at=started_at,
        git_sha=git_sha,
        prompt_versions=dict(prompt_versions or {}),
        label=label,
        case_set=case_set,
        summary={},
        verdict=None,
        created_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()
    return _harness_run_view(row)


async def add_harness_case_result(
    session: AsyncSession,
    *,
    run_id: UUID,
    case_id: str,
    case_type: str,
    layer: str,
    passed: bool,
    score: float | None = None,
    metrics: dict[str, Any] | None = None,
    trace: list[Any] | None = None,
) -> HarnessCaseResult:
    row = HarnessCaseResultRow(
        id=uuid4(),
        run_id=run_id,
        case_id=case_id,
        case_type=case_type,
        layer=layer,
        passed=passed,
        score=score,
        metrics=dict(metrics or {}),
        trace=list(trace or []),
        created_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()
    return _harness_case_view(row)


async def finalize_harness_run(
    session: AsyncSession,
    run_id: UUID,
    *,
    summary: dict[str, Any],
    verdict: str,
) -> None:
    row = await session.get(HarnessRunRow, run_id)
    if row is None:
        raise KeyError(f"harness run not found: {run_id}")
    row.summary = dict(summary)
    row.verdict = verdict
    await session.flush()


async def get_harness_run(
    session: AsyncSession,
    run_id: UUID,
) -> HarnessRun | None:
    row = await session.get(HarnessRunRow, run_id)
    if row is None:
        return None
    return _harness_run_view(row)


async def set_harness_decision(
    session: AsyncSession,
    run_id: UUID,
    *,
    decision: str,
    note: str | None = None,
    suite_version: str | None = None,
) -> HarnessRun:
    """Record human holdout decision on ``summary`` only.

    Audit-only: does **not** call ``register_prompts`` / ``install_skill`` or
    otherwise mutate prompts/skills. adopt ≠ auto-apply (VISION P5).

    Always stamps ``suite_version`` (explicit arg, else run summary, else
    current ``gotit.harness.SUITE_VERSION``) so adopt is pinned to a suite pin.
    """
    if decision not in {"adopt", "observe", "reject"}:
        raise ValueError(f"unknown harness decision: {decision}")
    row = await session.get(HarnessRunRow, run_id)
    if row is None:
        raise KeyError(f"harness run not found: {run_id}")
    from gotit.harness.suite import SUITE_VERSION

    summary = dict(row.summary or {})
    summary["decision"] = decision
    summary["decision_note"] = (note or "").strip() or None
    summary["decided_at"] = datetime.now(UTC).isoformat()
    pinned = (suite_version or "").strip() or None
    if pinned is None:
        existing = summary.get("suite_version")
        pinned = str(existing).strip() if existing else SUITE_VERSION
    summary["suite_version"] = pinned
    row.summary = summary
    await session.flush()
    return _harness_run_view(row)


async def list_harness_runs(
    session: AsyncSession,
    *,
    label: str | None = None,
    decision: str | None = None,
    limit: int = 50,
) -> list[HarnessRun]:
    """List runs newest-first. ``decision`` filters ``summary.decision`` (audit)."""
    # Over-fetch when filtering JSON audit field (SQLite/Postgres portable).
    fetch = limit * 5 if decision is not None else limit
    stmt = select(HarnessRunRow).order_by(HarnessRunRow.created_at.desc()).limit(fetch)
    if label is not None:
        stmt = stmt.where(HarnessRunRow.label == label)
    rows = list((await session.execute(stmt)).scalars().all())
    views = [_harness_run_view(r) for r in rows]
    if decision is not None:
        views = [v for v in views if (v.summary or {}).get("decision") == decision]
    return views[:limit]


async def list_harness_case_results(
    session: AsyncSession,
    *,
    run_id: UUID | None = None,
    case_id: str | None = None,
    limit: int = 200,
) -> list[HarnessCaseResult]:
    stmt = select(HarnessCaseResultRow).order_by(
        HarnessCaseResultRow.created_at.desc()
    ).limit(limit)
    if run_id is not None:
        stmt = stmt.where(HarnessCaseResultRow.run_id == run_id)
    if case_id is not None:
        stmt = stmt.where(HarnessCaseResultRow.case_id == case_id)
    rows = list((await session.execute(stmt)).scalars().all())
    return [_harness_case_view(r) for r in rows]
