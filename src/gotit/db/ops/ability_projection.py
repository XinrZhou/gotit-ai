"""Async loader for derived Ability State Projection (no new tables, no writes)."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gotit.core.ability_projection import (
    AbilityClaimInput,
    AbilityStateProjection,
    AbilityTrajectoryInput,
    assemble_ability_state,
)
from gotit.db.models import ClaimRow
from gotit.db.ops._common import DEFAULT_USER_ID
from gotit.db.ops.memory import list_memory, list_trajectory


async def build_ability_state(
    session: AsyncSession,
    *,
    user_id: str = DEFAULT_USER_ID,
    as_of: date | None = None,
    topic: str | None = None,
    trajectory_limit: int = 200,
    weak_point_limit: int = 5,
) -> AbilityStateProjection:
    """Read-only per-topic ability projection from claims + trajectory.

    Never writes mastery. Optional ``topic`` filters claim rows and trajectory.
    """
    day = as_of or date.today()
    stmt = select(ClaimRow).where(ClaimRow.user_id == user_id)
    if topic is not None:
        stmt = stmt.where(ClaimRow.topic == topic)
    rows = list((await session.execute(stmt)).scalars().all())
    claims = [
        AbilityClaimInput(
            id=r.id,
            text=r.text or "",
            topic=r.topic,
            status=str(r.status),
            next_review_at=r.next_review_at,
        )
        for r in rows
    ]

    traj_rows = await list_trajectory(
        session, user_id=user_id, topic=topic, limit=trajectory_limit
    )
    trajectory: list[AbilityTrajectoryInput] = []
    for e in traj_rows:
        raw_id = e.content.get("claim_id") or e.source.get("claim_id")
        cid: UUID | None
        try:
            cid = UUID(str(raw_id)) if raw_id else None
        except (TypeError, ValueError):
            cid = None
        gate = e.content.get("gate_verdict") or e.content.get("verdict")
        trajectory.append(
            AbilityTrajectoryInput(
                claim_id=cid,
                topic=e.topic,
                gate_verdict=str(gate) if gate else None,
                reason=str(e.content.get("reason") or "") or None,
            )
        )

    hints = await _fail_hints(session, user_id=user_id, claim_ids=[c.id for c in claims])
    return assemble_ability_state(
        as_of=day,
        user_id=user_id,
        claims=claims,
        trajectory=trajectory,
        fail_hints=hints,
        weak_point_limit=weak_point_limit,
    )


async def _fail_hints(
    session: AsyncSession,
    *,
    user_id: str,
    claim_ids: list[UUID],
) -> dict[UUID, str]:
    """Best-effort failure_digest excerpts keyed by claim (derived cache)."""
    if not claim_ids:
        return {}
    wanted = {str(cid) for cid in claim_ids}
    digests = await list_memory(
        session, user_id=user_id, kind="failure_digest", limit=80
    )
    out: dict[UUID, str] = {}
    for entry in digests:
        raw_id = entry.content.get("claim_id") or entry.source.get("claim_id")
        if raw_id is None or str(raw_id) not in wanted:
            continue
        try:
            cid = UUID(str(raw_id))
        except (TypeError, ValueError):
            continue
        if cid in out:
            continue
        follow = entry.content.get("follow_up") or entry.content.get("reason") or ""
        text = str(follow).strip()
        if text:
            out[cid] = text[:160]
    return out
