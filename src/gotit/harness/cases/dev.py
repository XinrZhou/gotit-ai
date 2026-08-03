"""Dev case set: lightweight cases that validate harness wiring without an LLM.

Layers covered: prompt (file loading), agent (construction), loop (verdict /
gate / routing / failure hook), system (DB two-table write + stub no-write).
Cases needing a session receive it via `build_dev_cases(session)`.

Contract rollups (metrics["rollup"]): gate_consistent | routing_ok |
no_spurious_write | failure_hook_ok — aggregated into HarnessRun.summary.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast
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
        # score signal: low score blocks pass even when agents agree
        g4 = deterministic_gate(
            "passed",
            "passed",
            score=0.2,
            evidence="enough evidence characters here",
        )
        # evidence signal: short/empty evidence downgrades passed → almost
        g5 = deterministic_gate("passed", "passed", evidence="short")
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
            and g4.verdict == "almost"
            and "low_score_blocks_pass" in g4.signals
            and g5.verdict == "almost"
            and "empty_evidence_blocks_pass" in g5.signals
        )
        return CaseResult(
            passed=ok,
            metrics={
                "rollup": "gate_consistent",
                "g1": g1.verdict,
                "g2": g2.verdict,
                "g3": g3.verdict,
                "g4": g4.verdict,
                "g5": g5.verdict,
            },
            trace=[
                {"g1": g1.model_dump(mode="json")},
                {"g2": g2.model_dump(mode="json")},
                {"g3": g3.model_dump(mode="json")},
                {"g4": g4.model_dump(mode="json")},
                {"g5": g5.model_dump(mode="json")},
            ],
        )

    return Case(
        case_id="gate-no-llm",
        case_type="deterministic_gate",
        layer="loop",
        runner=runner,
    )


def _case_check_routing() -> Case:
    """Form-follows-claim: APPLY/drill-no-project → probe; teach_back → teach."""

    async def runner() -> CaseResult:
        from gotit.core.check_routing import route_for_claim
        from gotit.core.models import CheckMode

        pid = uuid4()
        apply_r = route_for_claim(preferred=CheckMode.APPLY)
        drill_bare = route_for_claim(preferred=CheckMode.DRILL, project_id=None)
        drill_ok = route_for_claim(preferred=CheckMode.DRILL, project_id=pid)
        teach_r = route_for_claim(preferred=CheckMode.TEACH_BACK)
        probe_r = route_for_claim(preferred=None)

        rows: list[dict[str, Any]] = [
            {
                "pref": "apply",
                "mode": apply_r.mode.value,
                "open": apply_r.open_key,
                "expect": ("probe", "open_examine"),
            },
            {
                "pref": "drill/no-project",
                "mode": drill_bare.mode.value,
                "open": drill_bare.open_key,
                "expect": ("probe", "open_examine"),
            },
            {
                "pref": "drill+project",
                "mode": drill_ok.mode.value,
                "open": drill_ok.open_key,
                "expect": ("drill", "open_drill"),
            },
            {
                "pref": "teach_back",
                "mode": teach_r.mode.value,
                "open": teach_r.open_key,
                "cta": teach_r.cta_label,
                "expect": ("teach_back", "open_teach", "回讲"),
            },
            {
                "pref": "null",
                "mode": probe_r.mode.value,
                "open": probe_r.open_key,
                "expect": ("probe", "open_examine"),
            },
        ]
        ok = (
            apply_r.mode == CheckMode.PROBE
            and apply_r.open_key == "open_examine"
            and drill_bare.mode == CheckMode.PROBE
            and drill_bare.open_key == "open_examine"
            and drill_ok.mode == CheckMode.DRILL
            and drill_ok.open_key == "open_drill"
            and teach_r.mode == CheckMode.TEACH_BACK
            and teach_r.workflow == "teach"
            and teach_r.open_key == "open_teach"
            and teach_r.cta_label == "回讲"
            and probe_r.mode == CheckMode.PROBE
            and probe_r.open_key == "open_examine"
        )
        return CaseResult(
            passed=ok,
            metrics={"rollup": "routing_ok", "checks": len(rows)},
            trace=rows,
        )

    return Case(
        case_id="check-routing",
        case_type="check_routing",
        layer="loop",
        runner=runner,
    )


def _case_stub_no_spurious_write(session: AsyncSession) -> Case:
    """No-LLM stub path must not invent a stronger mastery writeback."""

    async def runner() -> CaseResult:
        from gotit.api.chat_orchestrator import _stub_turn
        from gotit.api.settings import Settings
        from gotit.core.agents.critic import stub_critic
        from gotit.core.loop import deterministic_gate

        # Critic stub echoes — never upgrades almost/owe_next → passed.
        c_almost = stub_critic(examine_verdict="almost")
        c_owe = stub_critic(examine_verdict="owe_next")
        gate_echo = deterministic_gate(c_almost.verdict, c_almost.verdict)
        critic_ok = (
            c_almost.verdict == "almost"
            and c_owe.verdict == "owe_next"
            and gate_echo.verdict == "almost"
            and not gate_echo.passed
        )

        # Companion stub turn is text-only (no tool_calls → no fake writes).
        turn = _stub_turn("axiom", "帮我开考", None)
        turn_ok = (
            "无 LLM key" in turn.text
            and turn.handoff_to is None
            and turn.thinking is None
        )

        # Empty LLM key gates companion tools off (chat_orchestrator contract).
        settings = Settings(llm_api_key="", critic_api_key="")
        tools_gated = not bool(settings.llm_api_key)

        # Explicit almost writeback must not mark mastered.
        claim_id = uuid4()
        user_id = "harness-stub"
        session.add(
            ClaimRow(
                id=claim_id,
                user_id=user_id,
                text="Stub must not forge mastery.",
                status=MasteryStatus.NOT_YET.value,
                topic="harness",
            )
        )
        await session.flush()
        wb = await day_ops.apply_examine_verdict(
            session,
            claim_id,
            verdict="almost",
            user_id=user_id,
            as_of=date(2026, 8, 1),
        )
        status = cast("dict[str, object]", wb["claim"])["status"]
        writeback_ok = status != MasteryStatus.MASTERED.value

        ok = critic_ok and turn_ok and tools_gated and writeback_ok
        return CaseResult(
            passed=ok,
            metrics={
                "rollup": "no_spurious_write",
                "critic_ok": critic_ok,
                "turn_ok": turn_ok,
                "tools_gated": tools_gated,
                "writeback_ok": writeback_ok,
                "status": status,
            },
            trace=[
                {"critic_almost": c_almost.verdict, "critic_owe": c_owe.verdict},
                {"stub_turn": turn.text[:80]},
                {"claim_id": str(claim_id), "status": status},
            ],
        )

    return Case(
        case_id="stub-no-spurious-write",
        case_type="stub_write",
        layer="system",
        runner=runner,
    )


def _case_failure_hook(session: AsyncSession) -> Case:
    """Failure digest + select/budget (existing API; aligns with direction B).

    Asserts: owe_next → digest exists → budgeted inject block non-empty ≤600;
    pure select/budget caps; passed does not invent almost/owe digest.
    If B later tightens re-examine inject, this case still locks the public API.
    """

    async def runner() -> CaseResult:
        from gotit.core.failure_lessons import (
            FAILURE_LESSON_MAX_CHARS,
            FAILURE_LESSON_MAX_ITEMS,
            FailureLessonCandidate,
            budget_failure_lesson_block,
            select_failure_lessons,
        )
        from gotit.db.ops import memory as memory_ops

        user_id = "harness-fail"
        claim_id = uuid4()
        session.add(
            ClaimRow(
                id=claim_id,
                user_id=user_id,
                text="Attention Q/K/V 容易搞混",
                status=MasteryStatus.NOT_YET.value,
                topic="transformers",
            )
        )
        await session.flush()

        wb = await day_ops.apply_examine_verdict(
            session,
            claim_id,
            verdict="owe_next",
            user_id=user_id,
            as_of=date(2026, 8, 1),
        )
        digest_id = wb.get("failure_digest_id")
        pending = await memory_ops.list_pending_failure_digests(
            session, user_id=user_id
        )
        digest_ok = digest_id is not None and len(pending) >= 1

        block = await memory_ops.build_failure_lesson_block(
            session,
            user_id=user_id,
            claim_id=claim_id,
            topic="transformers",
        )
        inject_ok = (
            block is not None
            and "栽过" in block
            and len(block) <= FAILURE_LESSON_MAX_CHARS
        )

        # Pure select + budget contract (no DB).
        neighbor = uuid4()
        cands = [
            FailureLessonCandidate(
                claim_id=str(claim_id),
                verdict="owe_next",
                claim_text="Attention Q/K/V 容易搞混",
                follow_up="Q/K/V 搞混了",
                topic="transformers",
                created_at=datetime.now(UTC),
            ),
            FailureLessonCandidate(
                claim_id=str(neighbor),
                verdict="almost",
                claim_text="neighbor tip",
                follow_up="neighbor miss",
                topic="other",
                created_at=datetime.now(UTC),
            ),
        ]
        selected = select_failure_lessons(
            cands,
            claim_id=claim_id,
            neighbor_ids=[neighbor],
            topic="transformers",
            max_items=FAILURE_LESSON_MAX_ITEMS,
        )
        budgeted = budget_failure_lesson_block(
            cands,
            claim_id=claim_id,
            neighbor_ids=[neighbor],
            topic="transformers",
        )
        pure_ok = (
            len(selected) >= 1
            and selected[0].claim_id == str(claim_id)
            and budgeted is not None
            and len(budgeted) <= FAILURE_LESSON_MAX_CHARS
        )

        # passed must not create an almost/owe_next digest for a fresh claim.
        pass_id = uuid4()
        session.add(
            ClaimRow(
                id=pass_id,
                user_id=user_id,
                text="Already solid claim",
                status=MasteryStatus.NOT_YET.value,
                topic="transformers",
            )
        )
        await session.flush()
        wb_pass = await day_ops.apply_examine_verdict(
            session,
            pass_id,
            verdict="passed",
            user_id=user_id,
            as_of=date(2026, 8, 1),
        )
        pass_ok = wb_pass.get("failure_digest_id") is None

        ok = digest_ok and inject_ok and pure_ok and pass_ok
        return CaseResult(
            passed=ok,
            metrics={
                "rollup": "failure_hook_ok",
                "digest_ok": digest_ok,
                "inject_ok": inject_ok,
                "pure_ok": pure_ok,
                "pass_ok": pass_ok,
                "block_chars": len(block or ""),
            },
            trace=[
                {"claim_id": str(claim_id), "digest_id": str(digest_id)},
                {"block_preview": (block or "")[:120]},
                {"selected_n": len(selected)},
            ],
        )

    return Case(
        case_id="failure-hook",
        case_type="failure_hook",
        layer="loop",
        runner=runner,
    )


def build_dev_cases(session: AsyncSession) -> list[Case]:
    return [
        _case_prompt_load(),
        _case_agent_build(),
        _case_loop_verdict(session),
        _case_gate_no_llm(),
        _case_check_routing(),
        _case_stub_no_spurious_write(session),
        _case_failure_hook(session),
        _case_system_two_tables(session),
    ]
