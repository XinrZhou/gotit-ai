"""System-level harness: run cases across 4 layers, persist to two tables.

Layers: prompt | agent | loop | system. A run creates one `harness_runs` row
and N `harness_case_results` rows. The runner is framework-light: it takes
callables and a writer; persistence is delegated to `gotit.db.ops`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from gotit.core.models import HarnessCaseResult, HarnessRun
from gotit.db import ops as day_ops


@dataclass
class CaseResult:
    passed: bool
    score: float | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    trace: list[dict[str, Any]] = field(default_factory=list)


CaseRunner = Callable[[], Awaitable[CaseResult]]


@dataclass(frozen=True)
class Case:
    case_id: str
    case_type: str
    layer: str  # prompt | agent | loop | system
    runner: CaseRunner


async def run_harness(
    session: AsyncSession,
    cases: list[Case],
    *,
    case_set: str,
    label: str | None = None,
    git_sha: str | None = None,
    prompt_versions: dict[str, str] | None = None,
) -> HarnessRun:
    """Execute cases, persist run + per-case results, return the run view."""
    started_at = datetime.now(UTC)
    run = await day_ops.add_harness_run(
        session,
        started_at=started_at,
        case_set=case_set,
        label=label,
        git_sha=git_sha,
        prompt_versions=prompt_versions or {},
    )

    passed = 0
    total = len(cases)
    for case in cases:
        result = await case.runner()
        if result.passed:
            passed += 1
        await day_ops.add_harness_case_result(
            session,
            run_id=run.id,
            case_id=case.case_id,
            case_type=case.case_type,
            layer=case.layer,
            passed=result.passed,
            score=result.score,
            metrics=result.metrics,
            trace=result.trace,
        )

    summary = {"total": total, "passed": passed, "failed": total - passed}
    verdict = "pass" if total > 0 and passed == total else "fail"
    await day_ops.finalize_harness_run(session, run.id, summary=summary, verdict=verdict)
    run.summary = summary
    run.verdict = verdict
    return run


__all__ = ["Case", "CaseResult", "CaseRunner", "HarnessCaseResult", "HarnessRun", "run_harness"]
