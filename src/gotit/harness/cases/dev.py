"""Dev case set: lightweight cases that validate harness wiring without an LLM.

Layers covered: prompt (file loading), agent (construction), loop (verdict
mapping), system (DB two-table write). Cases needing a session receive it via
`build_dev_cases(session)`.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from gotit.core.agents.axiom import build_axiom_agent
from gotit.core.agents.compass import build_compass_agent
from gotit.core.agents.echo import build_echo_agent
from gotit.core.models import MasteryStatus
from gotit.db import ops as day_ops
from gotit.db.models import ClaimRow
from gotit.harness import Case, CaseResult

PROMPTS_DIR = Path(__file__).resolve().parents[4] / "prompts"


def _case_prompt_load() -> Case:
    async def runner() -> CaseResult:
        from gotit.prompts import load_prompt_dir

        versions = load_prompt_dir(PROMPTS_DIR)
        agents = {v.agent_name for v in versions}
        ok = {"axiom", "compass", "echo"}.issubset(agents)
        return CaseResult(
            passed=ok,
            metrics={"count": len(versions), "agents": sorted(agents)},
            trace=[{"file": v.agent_name + ".md"} for v in versions],
        )

    return Case(
        case_id="prompt-load-all",
        case_type="prompt_load",
        layer="prompt",
        runner=runner,
    )


def _case_agent_build() -> Case:
    async def runner() -> CaseResult:
        from gotit.core.agents.llm import build_model

        model = build_model(
            base_url="https://api.openai.com/v1",
            api_key="sk-test",
            model_name="gpt-4.1-mini",
        )
        built = []
        for name, build in (
            ("axiom", build_axiom_agent),
            ("compass", build_compass_agent),
            ("echo", build_echo_agent),
        ):
            agent = build(model, system_prompt=f"test {name}")
            built.append({"agent": name, "name": agent.name})
        return CaseResult(passed=True, metrics={"built": len(built)}, trace=built)

    return Case(
        case_id="agent-build-all",
        case_type="agent_build",
        layer="agent",
        runner=runner,
    )


def _case_loop_verdict(session: AsyncSession) -> Case:
    async def runner() -> CaseResult:
        claim_id = uuid4()
        session.add(
            ClaimRow(
                id=claim_id,
                user_id="local",
                text="Dev case verdict mapping.",
                status=MasteryStatus.NOT_YET.value,
            )
        )
        await session.flush()
        wb = await day_ops.apply_examine_verdict(
            session, claim_id, verdict="passed", as_of=date(2026, 7, 28)
        )
        status = cast("dict[str, object]", wb["claim"])["status"]
        ok = status == MasteryStatus.MASTERED.value
        return CaseResult(
            passed=ok,
            metrics={"verdict": "passed", "status": status},
            trace=[{"claim_id": str(claim_id)}],
        )

    return Case(
        case_id="loop-verdict-passed",
        case_type="verdict_map",
        layer="loop",
        runner=runner,
    )


def _case_system_two_tables(session: AsyncSession) -> Case:
    async def runner() -> CaseResult:
        run = await day_ops.add_harness_run(
            session,
            started_at=datetime.now(UTC),
            case_set="dev",
        )
        await day_ops.add_harness_case_result(
            session,
            run_id=run.id,
            case_id="probe-1",
            case_type="smoke",
            layer="system",
            passed=True,
        )
        results = await day_ops.list_harness_case_results(session, run_id=run.id)
        ok = len(results) == 1 and results[0].passed
        return CaseResult(
            passed=ok,
            metrics={"results": len(results)},
            trace=[{"run_id": str(run.id)}],
        )

    return Case(
        case_id="system-two-tables",
        case_type="schema",
        layer="system",
        runner=runner,
    )


def _case_gate_no_llm() -> Case:
    """The mastery gate must be deterministic code, never an LLM call."""

    async def runner() -> CaseResult:
        from gotit.core.loop import deterministic_gate

        # stricter-of-two: passed + owe_next -> owe_next
        g1 = deterministic_gate("passed", "owe_next")
        # agreement: almost + almost -> almost (still due today)
        g2 = deterministic_gate("almost", "almost")
        # both pass -> passed, next_review_at cleared
        g3 = deterministic_gate("passed", "passed")
        ok = (
            g1.verdict == "owe_next"
            and g1.next_review_at is not None
            and g2.verdict == "almost"
            and g2.next_review_at is not None
            and g3.verdict == "passed"
            and g3.next_review_at is None
            and not g1.passed
            and not g2.passed
            and g3.passed
        )
        return CaseResult(
            passed=ok,
            metrics={
                "g1": g1.verdict,
                "g2": g2.verdict,
                "g3": g3.verdict,
            },
            trace=[
                {"g1": g1.model_dump(mode="json")},
                {"g2": g2.model_dump(mode="json")},
                {"g3": g3.model_dump(mode="json")},
            ],
        )

    return Case(
        case_id="gate-no-llm",
        case_type="deterministic_gate",
        layer="loop",
        runner=runner,
    )


def build_dev_cases(session: AsyncSession) -> list[Case]:
    return [
        _case_prompt_load(),
        _case_agent_build(),
        _case_loop_verdict(session),
        _case_gate_no_llm(),
        _case_system_two_tables(session),
    ]
