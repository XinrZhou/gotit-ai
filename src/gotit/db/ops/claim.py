"""Examine writeback and claim-listing operations."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gotit.core.check_routing import parse_check_mode
from gotit.core.models import CheckMode, Claim, MasteryStatus, PlanItemStatus
from gotit.core.schedule import schedule_after_verdict
from gotit.db.models import ClaimRow, PlanItemRow
from gotit.db.ops._common import DEFAULT_USER_ID, _claim_view, _plan_item_view

# Mastery row sources (routes/MCP must not invent new writers).
MASTERY_SOURCE_VERIFY = "verify"
MASTERY_SOURCE_CALIBRATION = "calibration"
MASTERY_SOURCE_HARNESS = "harness"


async def apply_examine_result(
    session: AsyncSession,
    claim_id: UUID,
    *,
    passed: bool,
    user_id: str = DEFAULT_USER_ID,
    as_of: date | None = None,
) -> dict[str, object]:
    """Deprecated binary stub writeback — prefer ``write_mastery_outcome``.

    Kept for harness/legacy tests only. Production verify/calib paths must not
    call this.
    """
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
        # Stub binary fail ≡ owe_next with no prior failures (interval = 1d).
        sched = schedule_after_verdict(
            "owe_next", prior_failures=0, as_of=today
        )
        claim.status = MasteryStatus.QUEUED.value
        claim.next_review_at = sched.next_review_at
        for item in items:
            item.status = PlanItemStatus.FAILED.value

    await session.flush()
    return {
        "claim": _claim_view(claim).model_dump(mode="json"),
        "plan_items": [_plan_item_view(i).model_dump(mode="json") for i in items],
        "passed": passed,
    }


async def write_mastery_outcome(
    session: AsyncSession,
    claim_id: UUID,
    *,
    verdict: str,
    source: str,
    user_id: str = DEFAULT_USER_ID,
    as_of: date | None = None,
    prior_failures: int = 0,
    follow_up: str | None = None,
    reason: str | None = None,
) -> dict[str, object]:
    """Single mastery-row writer: claim status + plan + failure_digest trigger.

    ``source`` documents the caller (verify | calibration | harness). Routes and
    MCP tools must not call this directly for verify — go through
    ``finalize_examine_with_gate``. Calibration may call with
    ``source=calibration`` (skips Critic/gate by design).

    Scheduling via ``schedule_after_verdict`` (never LLM):

    - passed     → MASTERED, plan VERIFIED, ``next_review_at`` cleared
    - almost     → IN_PROGRESS, plan IN_PROGRESS, due today (``as_of``)
    - owe_next   → QUEUED, plan FAILED, interval ``min(30, 1+2*prior_failures)``
    """
    today = as_of or date.today()
    claim = await session.get(ClaimRow, claim_id)
    if claim is None or claim.user_id != user_id:
        raise KeyError(f"claim not found: {claim_id}")

    stmt = select(PlanItemRow).where(PlanItemRow.claim_id == claim_id)
    items = list((await session.execute(stmt)).scalars().all())
    sched = schedule_after_verdict(
        verdict, prior_failures=prior_failures, as_of=today
    )

    if verdict == "passed":
        claim.status = MasteryStatus.MASTERED.value
        claim.next_review_at = sched.next_review_at
        for item in items:
            item.status = PlanItemStatus.VERIFIED.value
    elif verdict == "almost":
        claim.status = MasteryStatus.IN_PROGRESS.value
        claim.next_review_at = sched.next_review_at
        for item in items:
            item.status = PlanItemStatus.IN_PROGRESS.value
    elif verdict == "owe_next":
        claim.status = MasteryStatus.QUEUED.value
        claim.next_review_at = sched.next_review_at
        for item in items:
            item.status = PlanItemStatus.FAILED.value
    else:
        raise ValueError(f"unknown verdict: {verdict}")

    await session.flush()
    out: dict[str, object] = {
        "claim": _claim_view(claim).model_dump(mode="json"),
        "plan_items": [_plan_item_view(i).model_dump(mode="json") for i in items],
        "verdict": verdict,
        "schedule_reason": sched.reason_code,
        "interval_days": sched.interval_days,
        "source": source,
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
            follow_up=follow_up,
            reason=reason,
            source=source,
        )
        if digest is not None:
            out["failure_digest_id"] = str(digest.id)
    return out


async def apply_examine_verdict(
    session: AsyncSession,
    claim_id: UUID,
    *,
    verdict: str,
    user_id: str = DEFAULT_USER_ID,
    as_of: date | None = None,
    prior_failures: int = 0,
    follow_up: str | None = None,
    reason: str | None = None,
) -> dict[str, object]:
    """Thin alias → ``write_mastery_outcome`` (source=verify). Prefer the latter."""
    return await write_mastery_outcome(
        session,
        claim_id,
        verdict=verdict,
        source=MASTERY_SOURCE_VERIFY,
        user_id=user_id,
        as_of=as_of,
        prior_failures=prior_failures,
        follow_up=follow_up,
        reason=reason,
    )


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


async def set_claim_preferred_check_mode(
    session: AsyncSession,
    claim_id: UUID,
    *,
    preferred_check_mode: str | CheckMode | None,
    user_id: str = DEFAULT_USER_ID,
) -> Claim:
    """Set or clear preferred verify form (null = default probe)."""
    claim = await session.get(ClaimRow, claim_id)
    if claim is None or claim.user_id != user_id:
        raise KeyError(f"claim not found: {claim_id}")
    if preferred_check_mode is None or (
        isinstance(preferred_check_mode, str) and not preferred_check_mode.strip()
    ):
        claim.preferred_check_mode = None
    else:
        mode = parse_check_mode(preferred_check_mode)
        if mode is None:
            raise ValueError(f"unknown preferred_check_mode: {preferred_check_mode}")
        claim.preferred_check_mode = mode.value
    await session.flush()
    return _claim_view(claim)
