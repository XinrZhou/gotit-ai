"""Shared examine → Critic → WriteIntent → gate → commit finalize.

Phase-3 thin envelope (ADR-0004): LLM proposals enter ``WriteIntent`` only;
``deterministic_gate`` adjudicates; ``write_mastery_outcome`` remains the sole
mastery row writer. Gate thresholds and write semantics are unchanged.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from gotit.api.deps import (
    SessionMemoryReader,
    SessionPromptReader,
    get_critic_model,
    resolve_critic_binding,
)
from gotit.api.settings import Settings
from gotit.core.agent_run import (
    AgentRunKind,
    CommitReceipt,
    WriteIntent,
    evaluate_write_intent,
    intent_may_commit,
    make_commit_receipt,
    make_idempotency_key,
    new_agent_run,
    propose_write_intent,
    reject_write_intent,
)
from gotit.core.agents.critic import build_critic_agent, run_critic, stub_critic
from gotit.core.loop import VerifyWorkflow
from gotit.core.models import GateResult
from gotit.db import ops as day_ops
from gotit.db import session_scope
from gotit.db.models import ClaimRow


async def finalize_claim_by_id(
    *,
    claim_id: UUID,
    examine_verdict: str,
    user_id: str,
    settings: Settings,
    answer: str | None = None,
    thread_id: UUID | None = None,
    examine_score: float | None = None,
    examine_evidence: str | None = None,
    run_id: UUID | None = None,
) -> dict[str, Any]:
    """Load claim by id then ``finalize_examine_with_gate`` (REST + MCP entry)."""
    async with session_scope() as session:
        claim = await session.get(ClaimRow, claim_id)
        if claim is None or claim.user_id != user_id:
            raise KeyError(f"claim not found: {claim_id}")
        return await finalize_examine_with_gate(
            session,
            claim_id=claim_id,
            claim_text=claim.text,
            topic=claim.topic,
            examine_verdict=examine_verdict,
            examine_score=examine_score,
            examine_evidence=examine_evidence,
            learner_answer=answer,
            user_id=user_id,
            settings=settings,
            thread_id=thread_id,
            run_id=run_id,
        )


async def finalize_examine_with_gate(
    session: AsyncSession,
    *,
    claim_id: UUID,
    claim_text: str,
    topic: str | None,
    examine_verdict: str,
    user_id: str,
    settings: Settings,
    examine_score: float | None = None,
    examine_evidence: str | None = None,
    learner_answer: str | None = None,
    thread_id: UUID | None = None,
    run_id: UUID | None = None,
    kind: AgentRunKind = "verify",
) -> dict[str, Any]:
    """Recheck (Critic) → WriteIntent → gate → commit → trajectory + graph.

    Returns examine/recheck/gate fields, writeback, mastery_graph, plus
    ``run_id`` / ``write_intent`` / ``commit_receipt`` for audit.
    When ``thread_id`` is set, briefly records ball custody like thread verify.
    """
    from gotit.db.ops.claim import MASTERY_SOURCE_VERIFY, write_mastery_outcome
    from gotit.db.ops.graph import record_verify_mastery_writeback
    from gotit.db.ops.memory import (
        append_trajectory,
        count_prior_failures,
        list_trajectory,
        trajectory_has_idempotency_key,
    )

    run = new_agent_run(
        user_id=user_id,
        kind=kind,
        claim_id=claim_id,
        run_id=run_id,
        metadata={"thread_id": str(thread_id) if thread_id else None},
    )

    trajectory = await list_trajectory(
        session, user_id=user_id, topic=topic, claim_id=claim_id
    )
    prior_failures = count_prior_failures(trajectory, claim_id=claim_id)

    ball = None
    if thread_id is not None:
        ball = VerifyWorkflow.start(thread_id, claim_id)
        ball = VerifyWorkflow.on_examine(
            ball,
            verdict=examine_verdict,
            score=examine_score,
            evidence=examine_evidence,
        )
        await day_ops.set_ball(
            session,
            thread_id=thread_id,
            holder=ball.holder,
            stage=ball.stage,
            context=ball.context,
        )

    critic_identity = await day_ops.get_identity(session, "critic")
    critic_cfg = critic_identity.llm_config if critic_identity else None
    critic_binding = resolve_critic_binding(critic_cfg, settings=settings)
    if not critic_binding.api_key:
        recheck = stub_critic(examine_verdict=examine_verdict)
    else:
        cprompt = await SessionPromptReader(session).get_active_prompt("critic")
        csystem = cprompt.system_prompt if cprompt else ""
        creader = SessionMemoryReader(session, user_id=user_id)
        cagent = build_critic_agent(
            get_critic_model(critic_cfg, settings=settings),
            system_prompt=csystem,
        )
        recheck = await run_critic(
            cagent,
            creader,
            claim_text=claim_text,
            examine_verdict=examine_verdict,
            examine_score=examine_score,
            examine_evidence=examine_evidence,
            learner_answer=learner_answer,
        )

    # --- Propose (LLM outputs only enter WriteIntent) ---
    intent = propose_write_intent(
        run,
        claim_id=claim_id,
        examine_verdict=examine_verdict,
        recheck_verdict=recheck.verdict,
        examine_score=examine_score,
        examine_evidence=examine_evidence,
        prior_failures=prior_failures,
    )

    # --- Evaluate (gate is sole adjudicator; ball path preserves prior behavior) ---
    if ball is not None and thread_id is not None:
        ball = VerifyWorkflow.on_recheck(ball, verdict=recheck.verdict)
        await day_ops.set_ball(
            session,
            thread_id=thread_id,
            holder=ball.holder,
            stage=ball.stage,
            context=ball.context,
        )
        gate: GateResult = VerifyWorkflow.gate(
            ball, prior_failures=prior_failures
        )
        await day_ops.clear_ball(session, thread_id)
        # Align intent with the same gate result the ball path produced.
        intent = intent.model_copy(
            update={"status": "accepted", "gate": gate}
        )
    else:
        intent = evaluate_write_intent(intent)
        assert intent.gate is not None
        gate = intent.gate

    receipt, writeback, mastery, item_calibration = await _commit_accepted_intent(
        session,
        intent=intent,
        topic=topic,
        examine_verdict=examine_verdict,
        examine_score=examine_score,
        prior_trajectory=trajectory,
        write_mastery_outcome=write_mastery_outcome,
        append_trajectory=append_trajectory,
        record_verify_mastery_writeback=record_verify_mastery_writeback,
        trajectory_has_idempotency_key=trajectory_has_idempotency_key,
        mastery_source=MASTERY_SOURCE_VERIFY,
    )

    return {
        "examine_verdict": examine_verdict,
        "recheck_verdict": recheck.verdict,
        "gate": gate.model_dump(mode="json"),
        "gate_verdict": gate.verdict,
        "writeback": writeback,
        "mastery_graph": mastery,
        "calibration": item_calibration,
        "run_id": str(run.run_id),
        "write_intent": intent.model_dump(mode="json"),
        "commit_receipt": receipt.model_dump(mode="json"),
    }


async def _commit_accepted_intent(
    session: AsyncSession,
    *,
    intent: WriteIntent,
    topic: str | None,
    examine_verdict: str,
    examine_score: float | None,
    prior_trajectory: list[Any],
    write_mastery_outcome: Any,
    append_trajectory: Any,
    record_verify_mastery_writeback: Any,
    trajectory_has_idempotency_key: Any,
    mastery_source: str,
) -> tuple[CommitReceipt, dict[str, Any] | None, Any, Any]:
    """Commit only when ``intent_may_commit``; otherwise no mastery write."""
    if not intent_may_commit(intent):
        rejected = (
            intent
            if intent.status == "rejected"
            else reject_write_intent(intent, reason="intent_not_accepted")
        )
        receipt = make_commit_receipt(rejected, written=False)
        return receipt, None, None, None

    assert intent.gate is not None
    gate = intent.gate
    gate_reason = gate.reason
    idem_key = make_idempotency_key(
        run_id=intent.run_id,
        claim_id=intent.claim_id,
        gate_verdict=gate.verdict,
        gate_reason=gate_reason,
    )

    if trajectory_has_idempotency_key(prior_trajectory, idempotency_key=idem_key):
        # Same run envelope already committed — do not re-write mastery.
        from gotit.db.ops._common import _claim_view

        claim_row = await session.get(ClaimRow, intent.claim_id)
        status = claim_row.status if claim_row is not None else None
        writeback = {
            "claim": (
                _claim_view(claim_row).model_dump(mode="json")
                if claim_row is not None
                else {}
            ),
            "verdict": gate.verdict,
            "source": mastery_source,
            "run_id": str(intent.run_id),
            "idempotent": True,
        }
        receipt = make_commit_receipt(
            intent,
            written=False,
            idempotent=True,
            idempotency_key=idem_key,
            write_status=str(status) if status else None,
        )
        return receipt, writeback, None, None

    writeback = await write_mastery_outcome(
        session,
        intent.claim_id,
        verdict=gate.verdict,
        source=mastery_source,
        user_id=intent.user_id,
        prior_failures=intent.prior_failures,
        follow_up=gate_reason,
        reason=gate_reason,
    )

    item_calibration = await day_ops.apply_item_calibration_update(
        session,
        intent.claim_id,
        gate_verdict=gate.verdict,
        user_id=intent.user_id,
    )
    writeback["calibration"] = item_calibration
    writeback["run_id"] = str(intent.run_id)

    await append_trajectory(
        session,
        user_id=intent.user_id,
        claim_id=intent.claim_id,
        topic=topic,
        verdict=examine_verdict,
        gate_verdict=gate.verdict,
        score=examine_score,
        reason=gate_reason,
        source_kind=mastery_source,
        run_id=intent.run_id,
        idempotency_key=idem_key,
    )
    mastery = await record_verify_mastery_writeback(
        session,
        user_id=intent.user_id,
        claim_id=intent.claim_id,
        topic=topic,
        gate_verdict=gate.verdict,
        score=examine_score,
        reason=gate.reason,
    )

    claim_status = None
    if isinstance(writeback.get("claim"), dict):
        claim_status = writeback["claim"].get("status")
    receipt = make_commit_receipt(
        intent,
        written=True,
        write_status=str(claim_status) if claim_status else None,
        idempotency_key=idem_key,
    )
    return receipt, writeback, mastery, item_calibration


# Re-export for tests that need to assert envelope helpers without importing core.
__all__ = [
    "CommitReceipt",
    "WriteIntent",
    "finalize_claim_by_id",
    "finalize_examine_with_gate",
    "intent_may_commit",
    "propose_write_intent",
    "reject_write_intent",
]
