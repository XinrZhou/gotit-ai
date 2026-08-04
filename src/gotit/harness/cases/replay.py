"""Replay case set: lock Verify Spine contracts without a live LLM.

Fixtures feed fixed examine/recheck (or stub Critic via empty API keys) into
the same gate + ``write_mastery_outcome`` / ``finalize_examine_with_gate``
paths production uses. Asserts behavior contracts — not answer prose quality.
"""

from __future__ import annotations

from datetime import date
from typing import Any, cast
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from gotit.api.companion_tools import ToolCallRecorder, build_companion_tools
from gotit.api.verify_finalize import finalize_examine_with_gate
from gotit.core.agents.critic import stub_critic
from gotit.core.context_budget import ContextBudget, compose_examine_context
from gotit.core.loop import deterministic_gate
from gotit.core.models import MasteryStatus
from gotit.core.teach_verify import teach_examine_verdict
from gotit.db import ops as day_ops
from gotit.db.models import ThreadRow
from gotit.db.ops.claim import MASTERY_SOURCE_VERIFY
from gotit.harness import Case, CaseResult
from gotit.harness.cases._support import (
    claim_status,
    commit_after_gate,
    seed_claim,
    stub_settings,
    writeback_status,
)

_AS_OF = date(2026, 8, 3)
_USER = "replay-local"


def _case_gate_pass_mastery_write(session: AsyncSession) -> Case:
    """1. Normal gate pass → correct mastery write (stub Critic echoes)."""

    async def runner() -> CaseResult:
        claim_id = await seed_claim(
            session, user_id=_USER, text="Replay: solid pass path."
        )
        settings = stub_settings()
        out = await finalize_examine_with_gate(
            session,
            claim_id=claim_id,
            claim_text="Replay: solid pass path.",
            topic="replay",
            examine_verdict="passed",
            examine_score=0.9,
            examine_evidence="enough solid evidence here",
            user_id=_USER,
            settings=settings,
        )
        status = await claim_status(session, claim_id)
        ok = (
            out["gate_verdict"] == "passed"
            and out["recheck_verdict"] == "passed"
            and status == MasteryStatus.MASTERED.value
            and writeback_status(cast("dict[str, Any]", out["writeback"]))
            == MasteryStatus.MASTERED.value
        )
        return CaseResult(
            passed=ok,
            metrics={
                "rollup": "gate_consistent",
                "gate": out["gate_verdict"],
                "status": status,
            },
            trace=[{"claim_id": str(claim_id), "gate": out["gate"]}],
        )

    return Case(
        case_id="replay-gate-pass-write",
        case_type="replay_finalize",
        layer="system",
        runner=runner,
    )


def _case_critic_downgrade_blocks_pass(session: AsyncSession) -> Case:
    """2. Critic stricter than examine → must not write mastered.

    stub_critic echoes examine; replay injects a fixed recheck into the same
    gate+commit path finalize uses after Critic returns.
    """

    async def runner() -> CaseResult:
        claim_id = await seed_claim(
            session, user_id=_USER, text="Replay: critic downgrade."
        )
        gate, wb = await commit_after_gate(
            session,
            claim_id=claim_id,
            user_id=_USER,
            examine_verdict="passed",
            recheck_verdict="owe_next",
            score=0.95,
            evidence="plenty of examiner evidence text",
            as_of=_AS_OF,
        )
        status = writeback_status(wb)
        ok = (
            gate.verdict == "owe_next"
            and not gate.passed
            and status != MasteryStatus.MASTERED.value
        )
        return CaseResult(
            passed=ok,
            metrics={
                "rollup": "no_spurious_write",
                "gate": gate.verdict,
                "status": status,
            },
            trace=[{"claim_id": str(claim_id), "reason": gate.reason}],
        )

    return Case(
        case_id="replay-critic-downgrade",
        case_type="replay_gate",
        layer="loop",
        runner=runner,
    )


def _case_empty_evidence_blocks_pass(session: AsyncSession) -> Case:
    """3. Evidence too short → cannot pass even if agents agree."""

    async def runner() -> CaseResult:
        claim_id = await seed_claim(
            session, user_id=_USER, text="Replay: empty evidence."
        )
        settings = stub_settings()
        out = await finalize_examine_with_gate(
            session,
            claim_id=claim_id,
            claim_text="Replay: empty evidence.",
            topic="replay",
            examine_verdict="passed",
            examine_score=0.9,
            examine_evidence="short",
            user_id=_USER,
            settings=settings,
        )
        status = await claim_status(session, claim_id)
        signals = cast("dict[str, Any]", out["gate"]).get("signals") or []
        ok = (
            out["gate_verdict"] == "almost"
            and "empty_evidence_blocks_pass" in signals
            and status != MasteryStatus.MASTERED.value
        )
        return CaseResult(
            passed=ok,
            metrics={
                "rollup": "gate_consistent",
                "gate": out["gate_verdict"],
                "signals": list(signals),
                "status": status,
            },
            trace=[{"claim_id": str(claim_id)}],
        )

    return Case(
        case_id="replay-empty-evidence",
        case_type="replay_gate",
        layer="loop",
        runner=runner,
    )


def _case_prepare_only_no_mastery(session: AsyncSession) -> Case:
    """4. Companion start_examine prepare → claim mastery unchanged."""

    async def runner() -> CaseResult:
        claim_id = await seed_claim(
            session, user_id=_USER, text="Replay: prepare only."
        )
        before = await claim_status(session, claim_id)
        await day_ops.ensure_day(session, _AS_OF, user_id=_USER)
        rec = ToolCallRecorder()
        tools = build_companion_tools(
            session, user_id=_USER, day=_AS_OF, recorder=rec
        )
        start = next(t for t in tools if t.name == "start_examine")
        out = await start.function(claim_id=str(claim_id))
        after = await claim_status(session, claim_id)
        ok = (
            before == MasteryStatus.NOT_YET.value
            and after == MasteryStatus.NOT_YET.value
            and bool(out.get("ok"))
            and out.get("action") == "open_examine"
            and after != MasteryStatus.MASTERED.value
            and after != MasteryStatus.IN_PROGRESS.value
        )
        return CaseResult(
            passed=ok,
            metrics={
                "rollup": "no_spurious_write",
                "before": before,
                "after": after,
                "tool_calls": len(rec.calls),
            },
            trace=[{"claim_id": str(claim_id), "out_action": out.get("action")}],
        )

    return Case(
        case_id="replay-prepare-only",
        case_type="replay_prepare",
        layer="system",
        runner=runner,
    )


def _case_stub_llm_no_pollution(session: AsyncSession) -> Case:
    """5. Empty/abnormal LLM stub → no forged mastery upgrade."""

    async def runner() -> CaseResult:
        from gotit.api.chat_orchestrator import _stub_turn

        c_almost = stub_critic(examine_verdict="almost")
        c_owe = stub_critic(examine_verdict="owe_next")
        gate = deterministic_gate(c_almost.verdict, c_almost.verdict)
        turn = _stub_turn("axiom", "帮我开考", None)
        settings = stub_settings()

        claim_id = await seed_claim(
            session, user_id=_USER, text="Replay: stub must not forge pass."
        )
        out = await finalize_examine_with_gate(
            session,
            claim_id=claim_id,
            claim_text="Replay: stub must not forge pass.",
            topic="replay",
            examine_verdict="almost",
            examine_score=None,
            examine_evidence=None,
            user_id=_USER,
            settings=settings,
        )
        status = await claim_status(session, claim_id)
        ok = (
            c_almost.verdict == "almost"
            and c_owe.verdict == "owe_next"
            and gate.verdict == "almost"
            and not gate.passed
            and "无 LLM key" in turn.text
            and not bool(settings.llm_api_key)
            and out["gate_verdict"] == "almost"
            and status != MasteryStatus.MASTERED.value
        )
        return CaseResult(
            passed=ok,
            metrics={
                "rollup": "no_spurious_write",
                "status": status,
                "gate": out["gate_verdict"],
            },
            trace=[{"claim_id": str(claim_id), "stub": turn.text[:60]}],
        )

    return Case(
        case_id="replay-stub-no-pollution",
        case_type="replay_stub",
        layer="system",
        runner=runner,
    )


def _case_context_trim_keeps_graph() -> Case:
    """6. Context trim: over budget → lessons shrink/drop; graph preferred."""

    async def runner() -> CaseResult:
        from gotit.core.context_budget import compile_evidence_pack

        graph = "G" * 500
        lesson = "L" * 500
        blocks = compose_examine_context(
            graph,
            lesson,
            budget=ContextBudget(
                graph_max_chars=600, lesson_max_chars=600, total_max_chars=900
            ),
        )
        pack = compile_evidence_pack(
            recipe="probe",
            claim_id=None,
            graph_block=graph,
            lesson_block=lesson,
            budget=ContextBudget(
                graph_max_chars=600, lesson_max_chars=600, total_max_chars=900
            ),
        )
        graph_text = blocks.budget_block or ""
        lesson_text = blocks.failure_lesson_block
        total = len(graph_text) + (
            len(lesson_text) if lesson_text else 0
        ) + (2 if graph_text and lesson_text else 0)
        ok = (
            bool(graph_text)
            and total <= 900
            and (
                "lesson_dropped_for_total" in blocks.trim_signals
                or "lesson_trimmed_for_total" in blocks.trim_signals
                or (lesson_text is not None and len(lesson_text) < 500)
            )
            and bool(pack.pack_hash)
            and pack.trim_signals == tuple(blocks.trim_signals)
        )
        return CaseResult(
            passed=ok,
            metrics={
                "trim_signals": list(blocks.trim_signals),
                "graph_chars": len(graph_text),
                "lesson_chars": len(lesson_text) if lesson_text else 0,
                "total": total,
                "pack_hash": pack.pack_hash,
            },
            trace=[{"signals": list(blocks.trim_signals), "pack_hash": pack.pack_hash}],
        )

    return Case(
        case_id="replay-context-trim",
        case_type="replay_budget",
        layer="loop",
        runner=runner,
    )


def _case_pack_hash_stable(session: AsyncSession) -> Case:
    """EvidencePack hash stable for identical claim context (Phase 2)."""

    async def runner() -> CaseResult:
        from gotit.db.ops.evidence import build_evidence_pack_for_claim

        claim_id = await seed_claim(
            session, user_id=_USER, text="Replay: pack hash stability."
        )
        p1 = await build_evidence_pack_for_claim(
            session,
            claim_id=claim_id,
            user_id=_USER,
            topic="replay",
            recipe="probe",
            claim_text="Replay: pack hash stability.",
        )
        p2 = await build_evidence_pack_for_claim(
            session,
            claim_id=claim_id,
            user_id=_USER,
            topic="replay",
            recipe="probe",
            claim_text="Replay: pack hash stability.",
        )
        ok = p1.pack_hash == p2.pack_hash and bool(p1.pack_hash)
        return CaseResult(
            passed=ok,
            metrics={
                "pack_hash": p1.pack_hash,
                "trim": list(p1.trim_signals),
                "fingerprint": p1.snapshot_fingerprint,
            },
            trace=[{"claim_id": str(claim_id), "hash": p1.pack_hash}],
        )

    return Case(
        case_id="replay-pack-hash-stable",
        case_type="replay_pack",
        layer="system",
        runner=runner,
    )


def _case_idempotent_status(session: AsyncSession) -> Case:
    """7. Same run_id commit twice → second is idempotent (no double mastery write)."""

    async def runner() -> CaseResult:
        from uuid import uuid4

        from gotit.db.ops.memory import list_trajectory

        claim_id = await seed_claim(
            session, user_id=_USER, text="Replay: idempotent status."
        )
        settings = stub_settings()
        run_id = uuid4()
        kwargs: dict[str, Any] = {
            "claim_id": claim_id,
            "claim_text": "Replay: idempotent status.",
            "topic": "replay",
            "examine_verdict": "passed",
            "examine_score": 0.88,
            "examine_evidence": "stable evidence for pass gate",
            "user_id": _USER,
            "settings": settings,
            "run_id": run_id,
        }
        out1 = await finalize_examine_with_gate(session, **kwargs)
        status1 = await claim_status(session, claim_id)
        traj1 = await list_trajectory(
            session, user_id=_USER, claim_id=claim_id, limit=20
        )
        out2 = await finalize_examine_with_gate(session, **kwargs)
        status2 = await claim_status(session, claim_id)
        traj2 = await list_trajectory(
            session, user_id=_USER, claim_id=claim_id, limit=20
        )
        r1 = out1.get("commit_receipt") or {}
        r2 = out2.get("commit_receipt") or {}
        ok = (
            out1["gate_verdict"] == "passed"
            and out2["gate_verdict"] == "passed"
            and status1 == MasteryStatus.MASTERED.value
            and status2 == MasteryStatus.MASTERED.value
            and out1.get("run_id") == str(run_id)
            and bool(r1.get("written"))
            and r2.get("idempotent") is True
            and r2.get("written") is False
            and len(traj2) == len(traj1)  # no second trajectory row
        )
        return CaseResult(
            passed=ok,
            metrics={
                "rollup": "no_spurious_write",
                "status1": status1,
                "status2": status2,
                "traj_n": len(traj2),
                "idempotent": r2.get("idempotent"),
            },
            trace=[{"claim_id": str(claim_id), "run_id": str(run_id)}],
        )

    return Case(
        case_id="replay-idempotent-commit",
        case_type="replay_idempotent",
        layer="system",
        runner=runner,
    )


def _case_envelope_intent_through_gate(session: AsyncSession) -> Case:
    """WriteIntent proposals must go through gate; run_id on receipt + trajectory."""

    async def runner() -> CaseResult:
        from gotit.db.ops.memory import list_trajectory

        claim_id = await seed_claim(
            session, user_id=_USER, text="Replay: envelope gate path."
        )
        settings = stub_settings()
        out = await finalize_examine_with_gate(
            session,
            claim_id=claim_id,
            claim_text="Replay: envelope gate path.",
            topic="replay",
            examine_verdict="passed",
            examine_score=0.2,
            examine_evidence="enough evidence characters here",
            user_id=_USER,
            settings=settings,
        )
        intent = out.get("write_intent") or {}
        receipt = out.get("commit_receipt") or {}
        traj = await list_trajectory(
            session, user_id=_USER, claim_id=claim_id, limit=5
        )
        status = await claim_status(session, claim_id)
        # LLM proposed passed+score; gate must downgrade → almost, not mastered.
        gate_dump = intent.get("gate") or {}
        ok = (
            intent.get("examine_verdict") == "passed"
            and intent.get("status") == "accepted"
            and gate_dump.get("verdict") == "almost"
            and out["gate_verdict"] == "almost"
            and status != MasteryStatus.MASTERED.value
            and bool(out.get("run_id"))
            and str(receipt.get("run_id")) == str(out.get("run_id"))
            and receipt.get("written") is True
            and bool(traj)
            and traj[0].content.get("run_id") == out.get("run_id")
        )
        return CaseResult(
            passed=ok,
            metrics={
                "rollup": "gate_consistent",
                "gate": out["gate_verdict"],
                "run_id": out.get("run_id"),
            },
            trace=[{"claim_id": str(claim_id), "intent": intent.get("status")}],
        )

    return Case(
        case_id="replay-envelope-gate",
        case_type="replay_envelope",
        layer="system",
        runner=runner,
    )


def _case_rejected_intent_no_write(session: AsyncSession) -> Case:
    """Rejected WriteIntent must not call mastery write."""

    async def runner() -> CaseResult:
        from gotit.core.agent_run import (
            evaluate_write_intent,
            intent_may_commit,
            new_agent_run,
            propose_write_intent,
            reject_write_intent,
        )
        from gotit.db.ops.claim import write_mastery_outcome

        claim_id = await seed_claim(
            session, user_id=_USER, text="Replay: rejected intent."
        )
        before = await claim_status(session, claim_id)
        run = new_agent_run(user_id=_USER, claim_id=claim_id, kind="verify")
        intent = propose_write_intent(
            run,
            claim_id=claim_id,
            examine_verdict="passed",
            recheck_verdict="passed",
            examine_score=0.9,
            examine_evidence="enough evidence characters here",
        )
        intent = evaluate_write_intent(intent)
        rejected = reject_write_intent(intent, reason="test_reject")
        may = intent_may_commit(rejected)
        # Simulate commit guard used by finalize — must not write.
        if may:
            await write_mastery_outcome(
                session,
                claim_id,
                verdict="passed",
                source="harness",
                user_id=_USER,
            )
        after = await claim_status(session, claim_id)
        ok = (
            may is False
            and rejected.status == "rejected"
            and before == after
            and after != MasteryStatus.MASTERED.value
        )
        return CaseResult(
            passed=ok,
            metrics={
                "rollup": "no_spurious_write",
                "may_commit": may,
                "status": after,
            },
            trace=[{"claim_id": str(claim_id), "reason": rejected.reject_reason}],
        )

    return Case(
        case_id="replay-rejected-intent",
        case_type="replay_envelope",
        layer="loop",
        runner=runner,
    )


def _case_entry_parity(session: AsyncSession) -> Case:
    """8. Different entries → same gate/finalize behavior.

    Covers: direct finalize, thread-ball finalize, teach mapping → finalize.
    """

    async def runner() -> CaseResult:
        settings = stub_settings()
        evidence = "shared evidence string ok"
        # A: direct finalize
        a_id = await seed_claim(session, user_id=_USER, text="Replay entry A")
        a = await finalize_examine_with_gate(
            session,
            claim_id=a_id,
            claim_text="Replay entry A",
            topic="replay",
            examine_verdict="passed",
            examine_score=0.85,
            examine_evidence=evidence,
            user_id=_USER,
            settings=settings,
        )
        # B: with thread ball custody
        b_id = await seed_claim(session, user_id=_USER, text="Replay entry B")
        thread_id = uuid4()
        session.add(
            ThreadRow(
                id=thread_id,
                user_id=_USER,
                title="replay-thread",
            )
        )
        await session.flush()
        b = await finalize_examine_with_gate(
            session,
            claim_id=b_id,
            claim_text="Replay entry B",
            topic="replay",
            examine_verdict="passed",
            examine_score=0.85,
            examine_evidence=evidence,
            user_id=_USER,
            settings=settings,
            thread_id=thread_id,
        )
        # C: teach mapping → finalize
        c_id = await seed_claim(session, user_id=_USER, text="Replay entry C teach")
        teach_v = teach_examine_verdict(True)
        c = await finalize_examine_with_gate(
            session,
            claim_id=c_id,
            claim_text="Replay entry C teach",
            topic="replay",
            examine_verdict=teach_v,
            examine_score=0.85,
            examine_evidence=evidence,
            user_id=_USER,
            settings=settings,
        )
        # D: teach fail mapping must not master
        d_id = await seed_claim(session, user_id=_USER, text="Replay entry D teach fail")
        teach_fail = teach_examine_verdict(False)
        d = await finalize_examine_with_gate(
            session,
            claim_id=d_id,
            claim_text="Replay entry D teach fail",
            topic="replay",
            examine_verdict=teach_fail,
            user_id=_USER,
            settings=settings,
        )
        sa = await claim_status(session, a_id)
        sb = await claim_status(session, b_id)
        sc = await claim_status(session, c_id)
        sd = await claim_status(session, d_id)
        ok = (
            a["gate_verdict"] == b["gate_verdict"] == c["gate_verdict"] == "passed"
            and teach_v == "passed"
            and teach_fail == "owe_next"
            and d["gate_verdict"] == "owe_next"
            and sa == sb == sc == MasteryStatus.MASTERED.value
            and sd != MasteryStatus.MASTERED.value
            and a["writeback"].get("source") == MASTERY_SOURCE_VERIFY
        )
        return CaseResult(
            passed=ok,
            metrics={
                "rollup": "gate_consistent",
                "a": a["gate_verdict"],
                "b": b["gate_verdict"],
                "c": c["gate_verdict"],
                "d": d["gate_verdict"],
                "teach_map": teach_v,
            },
            trace=[
                {"a": str(a_id), "b": str(b_id), "c": str(c_id), "d": str(d_id)},
            ],
        )

    return Case(
        case_id="replay-entry-parity",
        case_type="replay_entries",
        layer="system",
        runner=runner,
    )


def _case_low_score_blocks_pass(session: AsyncSession) -> Case:
    """Bonus: low score signal blocks pass (same finalize path)."""

    async def runner() -> CaseResult:
        claim_id = await seed_claim(
            session, user_id=_USER, text="Replay: low score."
        )
        settings = stub_settings()
        out = await finalize_examine_with_gate(
            session,
            claim_id=claim_id,
            claim_text="Replay: low score.",
            topic="replay",
            examine_verdict="passed",
            examine_score=0.1,
            examine_evidence="enough evidence characters here",
            user_id=_USER,
            settings=settings,
        )
        signals = cast("dict[str, Any]", out["gate"]).get("signals") or []
        status = await claim_status(session, claim_id)
        ok = (
            out["gate_verdict"] == "almost"
            and "low_score_blocks_pass" in signals
            and status != MasteryStatus.MASTERED.value
        )
        return CaseResult(
            passed=ok,
            metrics={"gate": out["gate_verdict"], "signals": list(signals)},
            trace=[{"claim_id": str(claim_id)}],
        )

    return Case(
        case_id="replay-low-score",
        case_type="replay_gate",
        layer="loop",
        runner=runner,
    )


def build_replay_cases(session: AsyncSession) -> list[Case]:
    return [
        _case_gate_pass_mastery_write(session),
        _case_critic_downgrade_blocks_pass(session),
        _case_empty_evidence_blocks_pass(session),
        _case_prepare_only_no_mastery(session),
        _case_stub_llm_no_pollution(session),
        _case_context_trim_keeps_graph(),
        _case_pack_hash_stable(session),
        _case_idempotent_status(session),
        _case_envelope_intent_through_gate(session),
        _case_rejected_intent_no_write(session),
        _case_entry_parity(session),
        _case_low_score_blocks_pass(session),
    ]
