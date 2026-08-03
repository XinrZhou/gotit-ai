"""Shared helpers for MCP tool modules."""

from __future__ import annotations

from uuid import UUID

from gotit.api.settings import Settings, get_settings
from gotit.api.verify_finalize import finalize_claim_by_id


def _user_id() -> str:
    return get_settings().gotit_user_id


def _verify_meta(finalized: dict[str, object]) -> dict[str, object]:
    """Examine / recheck / gate fields for MCP responses (REST parity)."""
    return {
        "examine_verdict": finalized["examine_verdict"],
        "recheck_verdict": finalized["recheck_verdict"],
        "gate_verdict": finalized["gate_verdict"],
        "verdict": finalized["gate_verdict"],
    }


async def _finalize_claim_mcp(
    *,
    claim_id: UUID,
    examine_verdict: str,
    user_id: str,
    settings: Settings,
    answer: str | None = None,
    thread_id: UUID | None = None,
    examine_score: float | None = None,
    examine_evidence: str | None = None,
) -> dict[str, object]:
    """Critic → gate → writeback (shared with REST via ``finalize_claim_by_id``)."""
    return await finalize_claim_by_id(
        claim_id=claim_id,
        examine_verdict=examine_verdict,
        user_id=user_id,
        settings=settings,
        answer=answer,
        thread_id=thread_id,
        examine_score=examine_score,
        examine_evidence=examine_evidence,
    )
