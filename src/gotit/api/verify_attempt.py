"""Shared thread verify attempt: axiom (or stub) → finalize_examine_with_gate.

Chat REST and MCP ``gotit_start_verify`` must use this — do not fork gate writeback.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from gotit.api.action_blocks import attach_verdict_blocks
from gotit.api.deps import SessionMemoryReader, SessionPromptReader, get_model
from gotit.api.settings import Settings
from gotit.api.verify_finalize import finalize_examine_with_gate
from gotit.core.agents.axiom import build_axiom_agent, run_axiom
from gotit.db import ops as day_ops
from gotit.db.models import ClaimRow


async def run_verify_attempt(
    session: AsyncSession,
    *,
    thread_id: UUID,
    claim: ClaimRow,
    user_id: str,
    settings: Settings,
    answer: str | None = None,
    examine_verdict: str | None = None,
    persist_gate_message: bool = True,
) -> dict[str, Any]:
    """Examine → Critic → gate → writeback for one claim in a thread.

    Returns examine/recheck/gate/writeback/mastery_graph (same shape as before).
    """
    from gotit.db.ops.memory import list_trajectory

    claim_id = claim.id
    trajectory = await list_trajectory(
        session, user_id=user_id, topic=claim.topic, claim_id=claim_id
    )
    pack = await day_ops.build_evidence_pack_for_claim(
        session,
        claim_id=claim_id,
        user_id=user_id,
        topic=claim.topic,
        recipe="probe",
        claim_text=claim.text,
    )

    if examine_verdict is not None:
        ex_verdict = examine_verdict
        ex_score: float | None = None
        ex_evidence: str | None = None
    elif not settings.llm_api_key:
        ex_verdict = "passed"
        ex_score = None
        ex_evidence = None
    else:
        prompt = await SessionPromptReader(session).get_active_prompt("axiom")
        system_prompt = prompt.system_prompt if prompt else ""
        reader = SessionMemoryReader(session, user_id=user_id)
        agent = build_axiom_agent(get_model(), system_prompt=system_prompt)
        ev = await run_axiom(
            agent,
            reader,
            claim_text=claim.text,
            answer=answer,
            trajectory=trajectory,
            budget_block=pack.budget_block,
            failure_lesson_block=pack.failure_lesson_block,
        )
        ex_verdict = ev.verdict or "almost"
        ex_score = ev.score
        ex_evidence = ev.evidence

    finalized = await finalize_examine_with_gate(
        session,
        claim_id=claim_id,
        claim_text=claim.text,
        topic=claim.topic,
        examine_verdict=ex_verdict,
        examine_score=ex_score,
        examine_evidence=ex_evidence,
        learner_answer=answer,
        user_id=user_id,
        settings=settings,
        thread_id=thread_id,
    )

    gate = finalized["gate"]
    if persist_gate_message:
        verify_meta: dict[str, object] = {
            "claim_id": str(claim_id),
            "examine_verdict": finalized["examine_verdict"],
            "recheck_verdict": finalized["recheck_verdict"],
            "gate_verdict": finalized["gate_verdict"],
            "verdict": finalized["gate_verdict"],
            "pack_hash": pack.pack_hash,
            "trim_signals": list(pack.trim_signals),
        }
        attach_verdict_blocks(
            verify_meta,
            gate_verdict=str(finalized["gate_verdict"]),
            claim_id=claim_id,
        )
        await day_ops.add_message(
            session,
            thread_id=thread_id,
            role="agent",
            agent_name="gate",
            text=f"验证完成：{gate['reason']}",
            metadata=verify_meta,
        )

    return {
        "examine_verdict": finalized["examine_verdict"],
        "recheck_verdict": finalized["recheck_verdict"],
        "gate": gate,
        "writeback": finalized["writeback"],
        "mastery_graph": finalized["mastery_graph"],
        "evidence_pack": {
            "pack_hash": pack.pack_hash,
            "trim_signals": list(pack.trim_signals),
            "recipe": pack.recipe,
            "snapshot_fingerprint": pack.snapshot_fingerprint,
        },
    }
