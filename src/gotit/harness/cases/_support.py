"""Shared helpers for replay / holdout harness (no live LLM)."""

from __future__ import annotations

from datetime import date
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from gotit.api.settings import Settings
from gotit.core.loop import deterministic_gate
from gotit.core.models import GateResult, MasteryStatus
from gotit.db.models import ClaimRow
from gotit.db.ops.claim import MASTERY_SOURCE_VERIFY, write_mastery_outcome


def stub_settings() -> Settings:
    """Force Critic/chat onto stub paths — ignore ambient .env keys."""
    return Settings(llm_api_key="", critic_api_key="")


async def seed_claim(
    session: AsyncSession,
    *,
    user_id: str,
    text: str,
    topic: str = "replay",
    status: str = MasteryStatus.NOT_YET.value,
) -> UUID:
    claim_id = uuid4()
    session.add(
        ClaimRow(
            id=claim_id,
            user_id=user_id,
            text=text,
            status=status,
            topic=topic,
        )
    )
    await session.flush()
    return claim_id


async def claim_status(session: AsyncSession, claim_id: UUID) -> str:
    row = await session.get(ClaimRow, claim_id)
    assert row is not None
    return row.status


async def commit_after_gate(
    session: AsyncSession,
    *,
    claim_id: UUID,
    user_id: str,
    examine_verdict: str,
    recheck_verdict: str,
    score: float | None = None,
    evidence: str | None = None,
    prior_failures: int = 0,
    as_of: date | None = None,
) -> tuple[GateResult, dict[str, Any]]:
    """Evaluate+commit path used by finalize (without calling Critic LLM).

    Used when recheck must differ from examine (stub_critic only echoes).
    """
    gate = deterministic_gate(
        examine_verdict,
        recheck_verdict,
        score=score,
        evidence=evidence,
        prior_failures=prior_failures,
        as_of=as_of,
    )
    writeback = await write_mastery_outcome(
        session,
        claim_id,
        verdict=gate.verdict,
        source=MASTERY_SOURCE_VERIFY,
        user_id=user_id,
        as_of=as_of,
        prior_failures=prior_failures,
        follow_up=gate.reason,
        reason=gate.reason,
    )
    return gate, writeback


def writeback_status(writeback: dict[str, Any]) -> str:
    return str(cast("dict[str, object]", writeback["claim"])["status"])
