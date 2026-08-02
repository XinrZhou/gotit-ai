from __future__ import annotations

from uuid import UUID

from gotit.db import ops as day_ops
from gotit.db import session_scope
from gotit.db.runtime import ensure_db
from gotit.mcp.app import mcp
from gotit.mcp.common import (
    _user_id,
)


@mcp.tool()
async def gotit_calibration_start(
    note_id: str | None = None,
    topic: str | None = None,
    claim_ids: list[str] | None = None,
) -> dict[str, object]:
    """Start a cold-start calibration session (CAT-lite; no Critic)."""
    await ensure_db()
    ids = [UUID(c) for c in claim_ids] if claim_ids else None
    nid = UUID(note_id) if note_id else None
    async with session_scope() as session:
        view = await day_ops.start_calibration(
            session,
            user_id=_user_id(),
            note_id=nid,
            topic=topic,
            claim_ids=ids,
        )
        return view.model_dump(mode="json")

@mcp.tool()
async def gotit_calibration_answer(
    session_id: str,
    claim_id: str,
    outcome: str,
) -> dict[str, object]:
    """Answer one calibration item: outcome=correct|incorrect."""
    if outcome not in {"correct", "incorrect"}:
        raise ValueError("outcome must be correct or incorrect")
    await ensure_db()
    async with session_scope() as session:
        view = await day_ops.answer_calibration(
            session,
            UUID(session_id),
            claim_id=UUID(claim_id),
            outcome=outcome,  # type: ignore[arg-type]
            user_id=_user_id(),
        )
        return view.model_dump(mode="json")

@mcp.tool()
async def gotit_calibration_get(session_id: str) -> dict[str, object]:
    """Get calibration session + trace."""
    await ensure_db()
    async with session_scope() as session:
        view = await day_ops.get_calibration(
            session, UUID(session_id), user_id=_user_id()
        )
        return view.model_dump(mode="json")

@mcp.tool()
async def gotit_calibration_synthetic(
    true_theta: float,
    note_id: str | None = None,
    topic: str | None = None,
    claim_ids: list[str] | None = None,
    mode: str = "deterministic",
) -> dict[str, object]:
    """Replay calibration for a known ability; returns theta_hat and abs_error."""
    if mode not in {"deterministic", "bernoulli_threshold"}:
        raise ValueError("mode must be deterministic or bernoulli_threshold")
    await ensure_db()
    ids = [UUID(c) for c in claim_ids] if claim_ids else None
    nid = UUID(note_id) if note_id else None
    async with session_scope() as session:
        result = await day_ops.run_synthetic_calibration(
            session,
            true_theta=true_theta,
            note_id=nid,
            topic=topic,
            claim_ids=ids,
            user_id=_user_id(),
            mode=mode,  # type: ignore[arg-type]
        )
        return result.model_dump(mode="json")

