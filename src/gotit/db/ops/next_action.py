"""Async builder for state-driven ``next_action`` (shared REST / MCP / companion)."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from gotit.core.models import MasteryStatus
from gotit.core.next_action import (
    NextAction,
    NextActionClaimHint,
    NextActionState,
    next_action,
)
from gotit.db.models import ClaimRow
from gotit.db.ops._common import DEFAULT_USER_ID
from gotit.db.ops.ability_projection import build_ability_state
from gotit.db.ops.day import get_today


async def build_next_action(
    session: AsyncSession,
    *,
    user_id: str = DEFAULT_USER_ID,
    as_of: date | None = None,
) -> NextAction | None:
    """Load derived owed / ability / interview signals → ``next_action``.

    Read-only. Does not write mastery or start workflows.
    """
    day = as_of or date.today()
    today = await get_today(session, day, user_id=user_id)
    due = today.due_claims
    due_hints = [
        NextActionClaimHint(
            claim_id=c.id,
            preferred_check_mode=(
                c.preferred_check_mode.value
                if c.preferred_check_mode is not None
                else None
            ),
            project_id=c.project_id,
            due_reason_code=c.due_reason_code,
            topic=c.topic,
            text=c.text,
            status=c.status.value if hasattr(c.status, "value") else str(c.status),
        )
        for c in due[:8]
    ]

    ability = await build_ability_state(session, user_id=user_id, as_of=day)
    pending_total = sum(a.pending_review for a in ability.abilities)
    declining = next(
        (a.ability for a in ability.abilities if a.recent_trend == "declining"),
        None,
    )
    weak_hints: list[NextActionClaimHint] = []
    for a in ability.abilities:
        for w in a.weak_points:
            weak_hints.append(
                NextActionClaimHint(
                    claim_id=w.claim_id,
                    topic=a.ability if a.ability != "(untagged)" else None,
                    text=w.excerpt,
                    status=w.status,
                )
            )
        if len(weak_hints) >= 8:
            break

    claim_count = int(
        (
            await session.execute(
                select(func.count())
                .select_from(ClaimRow)
                .where(ClaimRow.user_id == user_id)
            )
        ).scalar_one()
    )
    mastered_count = int(
        (
            await session.execute(
                select(func.count())
                .select_from(ClaimRow)
                .where(
                    ClaimRow.user_id == user_id,
                    ClaimRow.status == MasteryStatus.MASTERED.value,
                )
            )
        ).scalar_one()
    )

    interview_drill = False
    interview_project: UUID | None = None
    if today.interview_focus is not None:
        interview_drill = True
        interview_project = today.interview_focus.project_id

    # Mirror Web cold-start CTA: nothing owed, library has examinable claims.
    calibration_eligible = len(due) == 0 and claim_count > 0 and mastered_count == 0

    state = NextActionState(
        as_of=day,
        user_id=user_id,
        due_claims=due_hints,
        weak_claims=weak_hints,
        interview_drill_suggested=interview_drill,
        interview_project_id=interview_project,
        claim_count=claim_count,
        mastered_count=mastered_count,
        pending_review_total=pending_total,
        declining_ability=declining,
        calibration_eligible=calibration_eligible,
    )
    return next_action(state)
