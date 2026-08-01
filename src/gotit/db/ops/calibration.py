"""Cold-start calibration sessions — CAT loop + schedule/graph writeback."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from gotit.core.calibration import (
    MAX_ITEMS,
    AbilityState,
    CalibItem,
    CalibOutcome,
    gate_verdict_to_outcome,
    item_from_meta,
    normalize_calibration_meta,
    select_next_item,
    should_stop,
    synthetic_outcome,
    update_ability,
    update_item_calibration,
)
from gotit.core.models import (
    CalibrationItemView,
    CalibrationSessionView,
    CalibrationSummary,
    MasteryStatus,
    SyntheticCalibrationResult,
)
from gotit.db.models import CalibrationSessionRow, ClaimRow
from gotit.db.ops._common import DEFAULT_USER_ID
from gotit.db.ops.claim import apply_examine_verdict
from gotit.db.ops.day import fill_today_from_queue, list_due_claims
from gotit.db.ops.graph import record_fail_event, seed_confused_for_calibration


def _meta_for_claim(row: ClaimRow) -> dict[str, object]:
    raw = row.calibration if isinstance(row.calibration, dict) else {}
    difficulty, discrimination, knowledge_key = normalize_calibration_meta(
        raw, topic=row.topic
    )
    return {
        "difficulty": difficulty,
        "discrimination": discrimination,
        "knowledge_key": knowledge_key,
    }


async def apply_item_calibration_update(
    session: AsyncSession,
    claim_id: UUID,
    *,
    outcome: CalibOutcome | None = None,
    gate_verdict: str | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> dict[str, object]:
    """Persist item a/b writeback from binary outcome or gate verdict."""
    if outcome is None:
        if not gate_verdict:
            raise ValueError("outcome or gate_verdict required")
        outcome = gate_verdict_to_outcome(gate_verdict)
    claim = await session.get(ClaimRow, claim_id)
    if claim is None or claim.user_id != user_id:
        raise KeyError(f"claim not found: {claim_id}")
    raw = claim.calibration if isinstance(claim.calibration, dict) else {}
    updated = update_item_calibration(raw, outcome=outcome, topic=claim.topic)
    claim.calibration = updated
    await session.flush()
    return dict(updated)


def _calib_item(row: ClaimRow) -> CalibItem:
    raw = row.calibration if isinstance(row.calibration, dict) else {}
    return item_from_meta(row.id, raw, topic=row.topic)


def _uuid_list(raw: list[Any] | None) -> list[UUID]:
    out: list[UUID] = []
    for x in raw or []:
        out.append(x if isinstance(x, UUID) else UUID(str(x)))
    return out


def _item_view(row: ClaimRow, *, n: int) -> CalibrationItemView:
    item = _calib_item(row)
    return CalibrationItemView(
        claim_id=row.id,
        text=row.text,
        topic=row.topic,
        difficulty=item.difficulty,
        discrimination=item.discrimination,
        knowledge_key=item.knowledge_key,
        n=n,
        max_items=MAX_ITEMS,
    )


def _summary_view(raw: dict[str, Any] | None) -> CalibrationSummary | None:
    if not raw:
        return None
    return CalibrationSummary.model_validate(raw)


def _session_view(
    row: CalibrationSessionRow,
    *,
    current: ClaimRow | None = None,
) -> CalibrationSessionView:
    done = row.status != "active"
    n_next = int(row.item_count) + 1
    return CalibrationSessionView(
        id=row.id,
        user_id=row.user_id,
        status=row.status,  # type: ignore[arg-type]
        theta=float(row.theta),
        se=float(row.se),
        item_count=int(row.item_count),
        stop_reason=row.stop_reason,
        scope=dict(row.scope or {}),
        trace=list(row.trace or []),
        summary=_summary_view(row.summary if row.summary else None),
        current_item=_item_view(current, n=n_next) if current is not None else None,
        done=done,
        created_at=row.created_at,
        completed_at=row.completed_at,
    )


async def _load_claims(
    session: AsyncSession,
    *,
    user_id: str,
    claim_ids: list[UUID],
) -> dict[UUID, ClaimRow]:
    if not claim_ids:
        return {}
    rows = list(
        (
            await session.execute(
                select(ClaimRow).where(
                    ClaimRow.user_id == user_id, ClaimRow.id.in_(claim_ids)
                )
            )
        )
        .scalars()
        .all()
    )
    return {r.id: r for r in rows}


async def _resolve_pool(
    session: AsyncSession,
    *,
    user_id: str,
    note_id: UUID | None,
    topic: str | None,
    claim_ids: list[UUID] | None,
) -> tuple[list[ClaimRow], dict[str, Any]]:
    scope: dict[str, Any] = {}
    if claim_ids:
        scope["claim_ids"] = [str(c) for c in claim_ids]
        rows = list(
            (
                await session.execute(
                    select(ClaimRow).where(
                        ClaimRow.user_id == user_id, ClaimRow.id.in_(claim_ids)
                    )
                )
            )
            .scalars()
            .all()
        )
        return rows, scope
    if note_id is not None:
        scope["note_id"] = str(note_id)
        rows = list(
            (
                await session.execute(
                    select(ClaimRow).where(
                        ClaimRow.user_id == user_id,
                        ClaimRow.source_note_id == note_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        return rows, scope
    if topic and topic.strip():
        scope["topic"] = topic.strip()
        rows = list(
            (
                await session.execute(
                    select(ClaimRow).where(
                        ClaimRow.user_id == user_id,
                        ClaimRow.topic == topic.strip(),
                    )
                )
            )
            .scalars()
            .all()
        )
        return rows, scope
    rows = list(
        (
            await session.execute(
                select(ClaimRow).where(
                    ClaimRow.user_id == user_id,
                    ClaimRow.status.in_(
                        [
                            MasteryStatus.NOT_YET.value,
                            MasteryStatus.QUEUED.value,
                        ]
                    ),
                    or_(
                        ClaimRow.next_review_at.is_(None),
                        ClaimRow.status == MasteryStatus.NOT_YET.value,
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    scope["default"] = "not_yet_pool"
    return rows, scope


def _pick_next(
    pool_rows: list[ClaimRow],
    *,
    answered: set[UUID],
    theta: float,
    last_key: str | None,
    downweight: set[UUID],
) -> tuple[ClaimRow | None, float, str]:
    candidates = [_calib_item(r) for r in pool_rows if r.id not in answered]
    by_id = {r.id: r for r in pool_rows}
    picked = select_next_item(
        candidates,
        theta=theta,
        last_knowledge_key=last_key,
        downweight_ids=downweight,
    )
    if picked is None:
        return None, 0.0, ""
    return by_id[picked.item.id], picked.info, picked.select_reason


async def _finalize(
    session: AsyncSession,
    row: CalibrationSessionRow,
    *,
    stop_reason: str,
    as_of: date,
    confused_seeded: int,
) -> CalibrationSessionView:
    user_id = row.user_id
    # Snapshot before other awaits — ORM may expire attrs after flush.
    trace_snap = list(row.trace or [])
    theta_snap = float(row.theta)
    se_snap = float(row.se)
    item_count_snap = int(row.item_count)
    await fill_today_from_queue(session, as_of, user_id=user_id)
    due = await list_due_claims(session, as_of, user_id=user_id)
    passed = sum(1 for t in trace_snap if t.get("outcome") == "correct")
    failed = sum(1 for t in trace_snap if t.get("outcome") == "incorrect")
    summary = {
        "passed_count": passed,
        "failed_count": failed,
        "confused_edges_seeded": confused_seeded,
        "due_count": len(due),
        "stop_reason": stop_reason,
        "theta": theta_snap,
        "se": se_snap,
        "item_count": item_count_snap,
    }
    row.status = "completed"
    row.stop_reason = stop_reason
    row.summary = summary
    row.trace = trace_snap
    row.current_claim_id = None
    row.completed_at = datetime.now(UTC)
    await session.flush()
    return _session_view(row, current=None)


async def start_calibration(
    session: AsyncSession,
    *,
    user_id: str = DEFAULT_USER_ID,
    note_id: UUID | None = None,
    topic: str | None = None,
    claim_ids: list[UUID] | None = None,
    as_of: date | None = None,
) -> CalibrationSessionView:
    """Open a calibration session and select the first item."""
    del as_of
    pool, scope = await _resolve_pool(
        session,
        user_id=user_id,
        note_id=note_id,
        topic=topic,
        claim_ids=claim_ids,
    )
    if not pool:
        raise ValueError("calibration pool is empty")

    for c in pool:
        meta = _meta_for_claim(c)
        if not c.calibration:
            c.calibration = meta

    answered: set[UUID] = set()
    downweight: set[UUID] = set()
    current, info, reason = _pick_next(
        pool,
        answered=answered,
        theta=3.0,
        last_key=None,
        downweight=downweight,
    )
    if current is None:
        raise ValueError("calibration pool is empty")
    _ = (info, reason)

    row = CalibrationSessionRow(
        id=uuid4(),
        user_id=user_id,
        status="active",
        theta=3.0,
        se=1.5,
        item_count=0,
        scope=scope,
        pool_claim_ids=[str(c.id) for c in pool],
        answered_claim_ids=[],
        downweight_claim_ids=[],
        last_knowledge_key=None,
        current_claim_id=current.id,
        recent_delta_theta=[],
        trace=[],
        summary={},
        created_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()
    return _session_view(row, current=current)


async def get_calibration(
    session: AsyncSession,
    session_id: UUID,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> CalibrationSessionView:
    row = await session.get(CalibrationSessionRow, session_id)
    if row is None or row.user_id != user_id:
        raise KeyError(f"calibration session not found: {session_id}")
    current = None
    if row.current_claim_id is not None and row.status == "active":
        current = await session.get(ClaimRow, row.current_claim_id)
        if current is not None and current.user_id != user_id:
            current = None
    return _session_view(row, current=current)


async def answer_calibration(
    session: AsyncSession,
    session_id: UUID,
    *,
    claim_id: UUID,
    outcome: CalibOutcome,
    user_id: str = DEFAULT_USER_ID,
    as_of: date | None = None,
) -> CalibrationSessionView:
    """Record one answer, writeback mastery/schedule, pick next or finalize."""
    today = as_of or date.today()
    row = await session.get(CalibrationSessionRow, session_id)
    if row is None or row.user_id != user_id:
        raise KeyError(f"calibration session not found: {session_id}")
    if row.status != "active":
        raise ValueError("calibration session is not active")
    if row.current_claim_id is None or row.current_claim_id != claim_id:
        raise ValueError("claim_id does not match current calibration item")

    claim = await session.get(ClaimRow, claim_id)
    if claim is None or claim.user_id != user_id:
        raise KeyError(f"claim not found: {claim_id}")

    item = _calib_item(claim)
    state = AbilityState(theta=float(row.theta), se=float(row.se))
    step = update_ability(
        state,
        outcome=outcome,
        discrimination=item.discrimination,
        difficulty=item.difficulty,
    )
    item_calib = await apply_item_calibration_update(
        session,
        claim_id,
        outcome=outcome,
        user_id=user_id,
    )
    # Reload claim params after writeback for trace (selection already used prior).
    claim = await session.get(ClaimRow, claim_id) or claim

    confused_seeded = 0
    if outcome == "correct":
        await apply_examine_verdict(
            session, claim_id, verdict="passed", user_id=user_id, as_of=today
        )
    else:
        await apply_examine_verdict(
            session, claim_id, verdict="almost", user_id=user_id, as_of=today
        )
        await record_fail_event(
            session,
            user_id=user_id,
            claim_id=claim_id,
            topic=claim.topic,
            gate_verdict="almost",
            reason="calibration",
        )
        pool_ids = _uuid_list(row.pool_claim_ids)
        confused_seeded = await seed_confused_for_calibration(
            session,
            user_id=user_id,
            failed_claim_id=claim_id,
            topic=claim.topic,
            pool_claim_ids=pool_ids,
            limit=2,
        )
        dw = set(_uuid_list(row.downweight_claim_ids))
        for cid in pool_ids:
            if cid == claim_id:
                continue
            peer = await session.get(ClaimRow, cid)
            if peer is None:
                continue
            if (peer.topic or "").strip() == (claim.topic or "").strip():
                dw.add(cid)
        row.downweight_claim_ids = [str(x) for x in dw]

    n = int(row.item_count) + 1
    delta = step.theta_after - step.theta_before
    recent = list(row.recent_delta_theta or [])
    recent.append(delta)
    if len(recent) > 8:
        recent = recent[-8:]

    trace_step = {
        "n": n,
        "claim_id": str(claim_id),
        "difficulty": item.difficulty,
        "discrimination": item.discrimination,
        "knowledge_key": item.knowledge_key,
        "theta_before": step.theta_before,
        "se_before": step.se_before,
        "info": step.info,
        "select_reason": "current",
        "outcome": outcome,
        "theta_after": step.theta_after,
        "se_after": step.se_after,
        "item_calibration": item_calib,
        "confused_edges_seeded": confused_seeded,
        "stop": False,
    }
    trace = list(row.trace or [])
    trace.append(trace_step)

    answered = set(_uuid_list(row.answered_claim_ids))
    answered.add(claim_id)

    row.theta = step.theta_after
    row.se = step.se_after
    row.item_count = n
    row.answered_claim_ids = [str(x) for x in answered]
    row.last_knowledge_key = item.knowledge_key
    row.recent_delta_theta = recent
    row.trace = trace

    pool_ids = _uuid_list(row.pool_claim_ids)
    claims_by_id = await _load_claims(session, user_id=user_id, claim_ids=pool_ids)
    pool_rows = [claims_by_id[i] for i in pool_ids if i in claims_by_id]
    remaining = [r for r in pool_rows if r.id not in answered]
    stop = should_stop(
        n_answered=n,
        se=float(row.se),
        recent_delta_theta=recent,
        candidates_remaining=len(remaining),
    )
    total_seeded = int((row.summary or {}).get("confused_edges_seeded", 0)) + confused_seeded
    row.summary = {
        **(row.summary or {}),
        "confused_edges_seeded": total_seeded,
    }

    if stop is not None:
        trace[-1]["stop"] = True
        row.trace = trace
        return await _finalize(
            session,
            row,
            stop_reason=stop,
            as_of=today,
            confused_seeded=total_seeded,
        )

    downweight = set(_uuid_list(row.downweight_claim_ids))
    nxt, info, reason = _pick_next(
        pool_rows,
        answered=answered,
        theta=float(row.theta),
        last_key=row.last_knowledge_key,
        downweight=downweight,
    )
    _ = (info, reason)
    if nxt is None:
        return await _finalize(
            session,
            row,
            stop_reason="exhausted",
            as_of=today,
            confused_seeded=total_seeded,
        )
    row.current_claim_id = nxt.id
    await session.flush()
    return _session_view(row, current=nxt)


async def run_synthetic_calibration(
    session: AsyncSession,
    *,
    true_theta: float,
    claim_ids: list[UUID] | None = None,
    note_id: UUID | None = None,
    topic: str | None = None,
    user_id: str = DEFAULT_USER_ID,
    mode: Literal["deterministic", "bernoulli_threshold"] = "deterministic",
    as_of: date | None = None,
) -> SyntheticCalibrationResult:
    """Replay calibration with a known ability; returns hat / error / trace."""
    today = as_of or date.today()
    view = await start_calibration(
        session,
        user_id=user_id,
        note_id=note_id,
        topic=topic,
        claim_ids=claim_ids,
        as_of=today,
    )
    guard = 0
    while not view.done and view.current_item is not None and guard < MAX_ITEMS + 2:
        guard += 1
        item = view.current_item
        outcome = synthetic_outcome(
            true_theta=true_theta,
            discrimination=item.discrimination,
            difficulty=item.difficulty,
            mode=mode,
        )
        view = await answer_calibration(
            session,
            view.id,
            claim_id=item.claim_id,
            outcome=outcome,
            user_id=user_id,
            as_of=today,
        )
    hat = float(view.theta)
    return SyntheticCalibrationResult(
        true_theta=true_theta,
        theta_hat=hat,
        abs_error=abs(hat - true_theta),
        item_count=view.item_count,
        stop_reason=view.stop_reason,
        trace=list(view.trace),
    )
