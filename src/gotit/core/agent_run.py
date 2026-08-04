"""Thin Verify Run envelope types (ADR-0004) — framework-free.

LLM outputs may only enter ``WriteIntent`` proposals. ``deterministic_gate``
adjudicates; ``CommitReceipt`` records the mastery write. No new authoritative
DB tables — ``run_id`` is audit metadata on trajectory / API return.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from gotit.core.models import GateResult

AgentRunKind = Literal["examine", "teach", "verify", "calibrate"]
WriteIntentStatus = Literal["proposed", "accepted", "rejected"]


class AgentRun(BaseModel):
    """Execution context for one verify-path close — not a business state row."""

    run_id: UUID = Field(default_factory=uuid4)
    user_id: str
    kind: AgentRunKind = "verify"
    claim_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WriteIntent(BaseModel):
    """Proposed mastery-related write — has no write authority.

    Only an ``accepted`` intent (post-gate) may enter commit. ``rejected``
    intents must not call ``write_mastery_outcome``.
    """

    intent_id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    claim_id: UUID
    user_id: str
    status: WriteIntentStatus = "proposed"
    # LLM / examiner proposals (never written directly as mastery).
    examine_verdict: str
    recheck_verdict: str
    examine_score: float | None = None
    examine_evidence: str | None = None
    prior_failures: int = 0
    # Filled after evaluate:
    gate: GateResult | None = None
    reject_reason: str | None = None


class CommitReceipt(BaseModel):
    """Audit receipt after commit (or skipped idempotent / rejected)."""

    run_id: UUID
    claim_id: UUID
    intent_id: UUID
    gate_verdict: str | None
    written: bool
    idempotent: bool = False
    idempotency_key: str | None = None
    write_status: str | None = None  # claim status after write, if any
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reject_reason: str | None = None


def new_agent_run(
    *,
    user_id: str,
    kind: AgentRunKind = "verify",
    claim_id: UUID | None = None,
    run_id: UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> AgentRun:
    return AgentRun(
        run_id=run_id or uuid4(),
        user_id=user_id,
        kind=kind,
        claim_id=claim_id,
        metadata=dict(metadata or {}),
    )


def propose_write_intent(
    run: AgentRun,
    *,
    claim_id: UUID,
    examine_verdict: str,
    recheck_verdict: str,
    examine_score: float | None = None,
    examine_evidence: str | None = None,
    prior_failures: int = 0,
) -> WriteIntent:
    """LLM/examiner proposals → WriteIntent (proposed). No DB writes."""
    return WriteIntent(
        run_id=run.run_id,
        claim_id=claim_id,
        user_id=run.user_id,
        status="proposed",
        examine_verdict=examine_verdict,
        recheck_verdict=recheck_verdict,
        examine_score=examine_score,
        examine_evidence=examine_evidence,
        prior_failures=prior_failures,
    )


def reject_write_intent(intent: WriteIntent, *, reason: str) -> WriteIntent:
    """Mark intent rejected — commit must refuse this intent."""
    return intent.model_copy(
        update={"status": "rejected", "reject_reason": reason, "gate": None}
    )


def evaluate_write_intent(intent: WriteIntent) -> WriteIntent:
    """Run deterministic_gate on proposals → accepted intent with GateResult.

    Does not write mastery. Rejected intents are returned unchanged.
    """
    from gotit.core.loop import deterministic_gate

    if intent.status == "rejected":
        return intent
    gate = deterministic_gate(
        intent.examine_verdict,
        intent.recheck_verdict,
        score=intent.examine_score,
        evidence=intent.examine_evidence,
        prior_failures=intent.prior_failures,
    )
    return intent.model_copy(update={"status": "accepted", "gate": gate})


def make_idempotency_key(
    *,
    run_id: UUID,
    claim_id: UUID,
    gate_verdict: str,
    gate_reason: str | None = None,
) -> str:
    raw = f"{run_id}:{claim_id}:{gate_verdict}:{gate_reason or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def make_commit_receipt(
    intent: WriteIntent,
    *,
    written: bool,
    write_status: str | None = None,
    idempotent: bool = False,
    idempotency_key: str | None = None,
) -> CommitReceipt:
    gate_verdict = intent.gate.verdict if intent.gate is not None else None
    return CommitReceipt(
        run_id=intent.run_id,
        claim_id=intent.claim_id,
        intent_id=intent.intent_id,
        gate_verdict=gate_verdict,
        written=written,
        idempotent=idempotent,
        idempotency_key=idempotency_key,
        write_status=write_status,
        reject_reason=intent.reject_reason,
    )


def intent_may_commit(intent: WriteIntent) -> bool:
    """Hard rule: only accepted intents with a gate result may commit."""
    return intent.status == "accepted" and intent.gate is not None


__all__ = [
    "AgentRun",
    "AgentRunKind",
    "CommitReceipt",
    "WriteIntent",
    "WriteIntentStatus",
    "evaluate_write_intent",
    "intent_may_commit",
    "make_commit_receipt",
    "make_idempotency_key",
    "new_agent_run",
    "propose_write_intent",
    "reject_write_intent",
]
