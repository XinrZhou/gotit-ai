"""Shared examine → Critic → deterministic gate → writeback finalize."""

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
from gotit.core.agents.critic import build_critic_agent, run_critic, stub_critic
from gotit.core.loop import VerifyWorkflow, deterministic_gate
from gotit.core.models import GateResult
from gotit.db import ops as day_ops


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
) -> dict[str, Any]:
    """Recheck (Critic) → gate → apply verdict → trajectory + mastery graph.

    Returns examine/recheck/gate fields, writeback, and mastery_graph summary.
    When ``thread_id`` is set, briefly records ball custody like thread verify.
    """
    from gotit.db.ops.graph import record_verify_mastery_writeback
    from gotit.db.ops.memory import (
        append_trajectory,
        count_prior_failures,
        list_trajectory,
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
    else:
        gate = deterministic_gate(
            examine_verdict=examine_verdict,
            recheck_verdict=recheck.verdict,
            score=examine_score,
            evidence=examine_evidence,
            prior_failures=prior_failures,
        )

    writeback = await day_ops.apply_examine_verdict(
        session,
        claim_id,
        verdict=gate.verdict,
        user_id=user_id,
        prior_failures=prior_failures,
    )

    await append_trajectory(
        session,
        user_id=user_id,
        claim_id=claim_id,
        topic=topic,
        verdict=examine_verdict,
        gate_verdict=gate.verdict,
        score=examine_score,
        reason=gate.reason,
    )
    mastery = await record_verify_mastery_writeback(
        session,
        user_id=user_id,
        claim_id=claim_id,
        topic=topic,
        gate_verdict=gate.verdict,
        score=examine_score,
        reason=gate.reason,
    )

    return {
        "examine_verdict": examine_verdict,
        "recheck_verdict": recheck.verdict,
        "gate": gate.model_dump(mode="json"),
        "gate_verdict": gate.verdict,
        "writeback": writeback,
        "mastery_graph": mastery,
    }
