"""System-level harness: run cases across 4 layers, persist to two tables.

Layers: prompt | agent | loop | system. A run creates one `harness_runs` row
and N `harness_case_results` rows. The runner is framework-light: it takes
callables and a writer; persistence is delegated to `gotit.db.ops`.

Run ``summary`` always carries total/passed/failed plus the eval-loop contract
keys (see ``CONTRACT_ROLLUP_KEYS``). Cases opt in via ``metrics["rollup"]``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from gotit.core.models import HarnessCaseResult, HarnessRun
from gotit.db import ops as day_ops

# Stable summary keys for gate.sh / CLI / REST / interview docs.
# Cases set metrics["rollup"] to one of these; runner rolls bool ok.
CONTRACT_ROLLUP_KEYS: tuple[str, ...] = (
    "gate_consistent",
    "routing_ok",
    "no_spurious_write",
    "failure_hook_ok",
)


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


@dataclass(frozen=True)
class _CaseOutcome:
    case_id: str
    case_type: str
    passed: bool
    metrics: dict[str, Any]


def aggregate_run_summary(
    outcomes: Sequence[_CaseOutcome] | Sequence[dict[str, Any]],
    *,
    total: int | None = None,
    passed: int | None = None,
) -> dict[str, Any]:
    """Build the stable harness summary (counts + contract rollups).

    Contract keys are flat bools: True when every tagged case passed, or when
    no case opted into that rollup (vacuous ok — gold may omit routing etc.).
    """
    parsed: list[_CaseOutcome] = []
    for item in outcomes:
        if isinstance(item, _CaseOutcome):
            parsed.append(item)
        else:
            parsed.append(
                _CaseOutcome(
                    case_id=str(item.get("case_id") or ""),
                    case_type=str(item.get("case_type") or ""),
                    passed=bool(item.get("passed")),
                    metrics=dict(item.get("metrics") or {}),
                )
            )

    n_total = total if total is not None else len(parsed)
    n_passed = passed if passed is not None else sum(1 for o in parsed if o.passed)
    summary: dict[str, Any] = {
        "total": n_total,
        "passed": n_passed,
        "failed": n_total - n_passed,
    }
    for key in CONTRACT_ROLLUP_KEYS:
        tagged = [o for o in parsed if o.metrics.get("rollup") == key]
        summary[key] = all(o.passed for o in tagged) if tagged else True
    return summary


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

    outcomes: list[_CaseOutcome] = []
    for case in cases:
        result = await case.runner()
        outcomes.append(
            _CaseOutcome(
                case_id=case.case_id,
                case_type=case.case_type,
                passed=result.passed,
                metrics=result.metrics,
            )
        )
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

    summary = aggregate_run_summary(outcomes)
    n_passed = int(summary["passed"])
    n_total = int(summary["total"])
    verdict = "pass" if n_total > 0 and n_passed == n_total else "fail"
    await day_ops.finalize_harness_run(session, run.id, summary=summary, verdict=verdict)
    run.summary = summary
    run.verdict = verdict
    return run


__all__ = [
    "CONTRACT_ROLLUP_KEYS",
    "Case",
    "CaseResult",
    "CaseRunner",
    "HarnessCaseResult",
    "HarnessRun",
    "aggregate_run_summary",
    "run_harness",
]
