"""REST: harness runs + human adopt/observe/reject decisions."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from gotit.api.auth import require_api_key
from gotit.core.models import HarnessCaseResult, HarnessRun
from gotit.db import ops as day_ops
from gotit.db import session_scope
from gotit.harness import run_harness
from gotit.harness.cases.dev import build_dev_cases
from gotit.harness.cases.gold import build_gold_cases

router = APIRouter()

CaseSetName = Literal["dev", "gold"]
DecisionName = Literal["adopt", "observe", "reject"]


class HarnessRunCreate(BaseModel):
    case_set: CaseSetName = "dev"
    label: str | None = Field(default=None, max_length=64)


class HarnessDecisionIn(BaseModel):
    decision: DecisionName
    note: str | None = Field(default=None, max_length=500)


class HarnessRunDetail(BaseModel):
    run: HarnessRun
    cases: list[HarnessCaseResult]


def _build_cases(session: Any, case_set: CaseSetName) -> list[Any]:
    if case_set == "dev":
        return build_dev_cases(session)
    if case_set == "gold":
        return build_gold_cases(session)
    raise ValueError(f"unknown case_set: {case_set}")


@router.post(
    "/v1/harness/runs",
    response_model=HarnessRunDetail,
    dependencies=[Depends(require_api_key)],
)
async def create_harness_run(body: HarnessRunCreate) -> HarnessRunDetail:
    async with session_scope() as session:
        cases = _build_cases(session, body.case_set)
        run = await run_harness(
            session,
            cases,
            case_set=body.case_set,
            label=body.label,
        )
        # Re-load after finalize (summary/verdict filled).
        fresh = await day_ops.get_harness_run(session, run.id)
        assert fresh is not None
        case_rows = await day_ops.list_harness_case_results(
            session, run_id=run.id, limit=200
        )
        # Oldest-first for UI reading order.
        case_rows = list(reversed(case_rows))
        return HarnessRunDetail(run=fresh, cases=case_rows)


@router.get(
    "/v1/harness/runs",
    response_model=list[HarnessRun],
    dependencies=[Depends(require_api_key)],
)
async def list_runs(
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    label: str | None = None,
    decision: DecisionName | None = None,
) -> list[HarnessRun]:
    async with session_scope() as session:
        return await day_ops.list_harness_runs(
            session, label=label, decision=decision, limit=limit
        )


@router.get(
    "/v1/harness/runs/{run_id}",
    response_model=HarnessRunDetail,
    dependencies=[Depends(require_api_key)],
)
async def get_run(run_id: UUID) -> HarnessRunDetail:
    async with session_scope() as session:
        run = await day_ops.get_harness_run(session, run_id)
        if run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="harness run not found"
            )
        cases = await day_ops.list_harness_case_results(
            session, run_id=run_id, limit=200
        )
        return HarnessRunDetail(run=run, cases=list(reversed(cases)))


@router.patch(
    "/v1/harness/runs/{run_id}",
    response_model=HarnessRun,
    dependencies=[Depends(require_api_key)],
)
async def decide_run(run_id: UUID, body: HarnessDecisionIn) -> HarnessRun:
    async with session_scope() as session:
        try:
            return await day_ops.set_harness_decision(
                session,
                run_id,
                decision=body.decision,
                note=body.note,
            )
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc
