"""Examine writeback and claim-listing operations."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gotit.core.models import Claim, MasteryStatus, PlanItemStatus
from gotit.db.models import ClaimRow, PlanItemRow
from gotit.db.ops._common import DEFAULT_USER_ID, _claim_view, _plan_item_view


async def apply_examine_result(
    session: AsyncSession,
    claim_id: UUID,
    *,
    passed: bool,
    user_id: str = DEFAULT_USER_ID,
    as_of: date | None = None,
) -> dict[str, object]:
    """Writeback claim + linked plan items after an examine attempt (stub-friendly)."""
    today = as_of or date.today()
    claim = await session.get(ClaimRow, claim_id)
    if claim is None or claim.user_id != user_id:
        raise KeyError(f"claim not found: {claim_id}")

    stmt = select(PlanItemRow).where(PlanItemRow.claim_id == claim_id)
    items = list((await session.execute(stmt)).scalars().all())

    if passed:
        claim.status = MasteryStatus.MASTERED.value
        claim.next_review_at = None
        for item in items:
            item.status = PlanItemStatus.VERIFIED.value
    else:
        claim.status = MasteryStatus.QUEUED.value
        claim.next_review_at = today + timedelta(days=1)
        for item in items:
            item.status = PlanItemStatus.FAILED.value

    await session.flush()
    return {
        "claim": _claim_view(claim).model_dump(mode="json"),
        "plan_items": [_plan_item_view(i).model_dump(mode="json") for i in items],
        "passed": passed,
    }


async def apply_examine_verdict(
    session: AsyncSession,
    claim_id: UUID,
    *,
    verdict: str,
    user_id: str = DEFAULT_USER_ID,
    as_of: date | None = None,
    prior_failures: int = 0,
) -> dict[str, object]:
    """Writeback for continuous verdicts: passed | almost | owe_next.

    - passed     → claim MASTERED, plan items VERIFIED
    - almost     → claim IN_PROGRESS, plan items IN_PROGRESS (stays today)
    - owe_next   → claim QUEUED, plan items FAILED, next_review_at grows with
                  prior failures on this claim (forgetting-curve weighting;
                  SM-2 remains out of scope): interval = 1 + 2*prior_failures.
    """
    today = as_of or date.today()
    claim = await session.get(ClaimRow, claim_id)
    if claim is None or claim.user_id != user_id:
        raise KeyError(f"claim not found: {claim_id}")

    stmt = select(PlanItemRow).where(PlanItemRow.claim_id == claim_id)
    items = list((await session.execute(stmt)).scalars().all())

    if verdict == "passed":
        claim.status = MasteryStatus.MASTERED.value
        claim.next_review_at = None
        for item in items:
            item.status = PlanItemStatus.VERIFIED.value
    elif verdict == "almost":
        claim.status = MasteryStatus.IN_PROGRESS.value
        for item in items:
            item.status = PlanItemStatus.IN_PROGRESS.value
    elif verdict == "owe_next":
        claim.status = MasteryStatus.QUEUED.value
        interval = 1 + 2 * max(prior_failures, 0)
        claim.next_review_at = today + timedelta(days=interval)
        for item in items:
            item.status = PlanItemStatus.FAILED.value
    else:
        raise ValueError(f"unknown verdict: {verdict}")

    await session.flush()
    out: dict[str, object] = {
        "claim": _claim_view(claim).model_dump(mode="json"),
        "plan_items": [_plan_item_view(i).model_dump(mode="json") for i in items],
        "verdict": verdict,
    }
    if verdict in {"almost", "owe_next"}:
        from gotit.db.ops.memory import maybe_record_failure_digest

        digest = await maybe_record_failure_digest(
            session,
            user_id=user_id,
            claim_id=claim_id,
            claim_text=claim.text,
            topic=claim.topic,
            verdict=verdict,
        )
        if digest is not None:
            out["failure_digest_id"] = str(digest.id)
    return out


async def list_topic_claims_today(
    session: AsyncSession,
    topic: str,
    *,
    user_id: str = DEFAULT_USER_ID,
    as_of: date | None = None,
) -> list[Claim]:
    """Today's plan-item claims matching `topic` and not yet mastered."""
    from gotit.db.ops.day import ensure_day

    target = as_of or date.today()
    learning_day = await ensure_day(session, target, user_id=user_id)
    item_claim_ids = [i.claim_id for i in learning_day.plan_items if i.claim_id]
    if not item_claim_ids:
        return []
    order = {i.claim_id: i.sort_order for i in learning_day.plan_items if i.claim_id}
    stmt = select(ClaimRow).where(
        ClaimRow.user_id == user_id,
        ClaimRow.id.in_(item_claim_ids),
        ClaimRow.topic == topic,
        ClaimRow.status != MasteryStatus.MASTERED.value,
    )
    rows = list((await session.execute(stmt)).scalars().all())
    rows.sort(key=lambda r: (order.get(r.id, 0), str(r.id)))
    return [_claim_view(r) for r in rows]


async def list_project_claims(
    session: AsyncSession,
    project_id: UUID,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> list[Claim]:
    stmt = select(ClaimRow).where(
        ClaimRow.project_id == project_id, ClaimRow.user_id == user_id
    )
    rows = list((await session.execute(stmt)).scalars().all())
    return [_claim_view(r) for r in rows]
