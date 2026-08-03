"""Long/working/session memory entries."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gotit.core.models import MemoryEntry
from gotit.db.models import MemoryEntryRow


def _memory_view(row: MemoryEntryRow) -> MemoryEntry:
    return MemoryEntry(
        id=row.id,
        user_id=row.user_id,
        layer=row.layer,
        kind=row.kind,
        topic=row.topic,
        content=dict(row.content or {}),
        source=dict(row.source or {}),
        created_at=row.created_at or datetime.now(UTC),
        expires_at=row.expires_at,
    )


async def add_memory(
    session: AsyncSession,
    *,
    user_id: str,
    layer: str,
    kind: str,
    content: dict[str, Any],
    topic: str | None = None,
    source: dict[str, Any] | None = None,
    expires_at: datetime | None = None,
) -> MemoryEntry:
    row = MemoryEntryRow(
        id=uuid4(),
        user_id=user_id,
        layer=layer,
        kind=kind,
        topic=topic,
        content=dict(content),
        source=dict(source or {}),
        created_at=datetime.now(UTC),
        expires_at=expires_at,
    )
    session.add(row)
    await session.flush()
    return _memory_view(row)


async def list_memory(
    session: AsyncSession,
    *,
    user_id: str,
    layer: str | None = None,
    kind: str | None = None,
    topic: str | None = None,
    limit: int = 50,
) -> list[MemoryEntry]:
    stmt = select(MemoryEntryRow).where(MemoryEntryRow.user_id == user_id)
    if layer is not None:
        stmt = stmt.where(MemoryEntryRow.layer == layer)
    if kind is not None:
        stmt = stmt.where(MemoryEntryRow.kind == kind)
    if topic is not None:
        stmt = stmt.where(MemoryEntryRow.topic == topic)
    stmt = stmt.order_by(MemoryEntryRow.created_at.desc()).limit(limit)
    rows = list((await session.execute(stmt)).scalars().all())
    return [_memory_view(r) for r in rows]


async def append_trajectory(
    session: AsyncSession,
    *,
    user_id: str,
    claim_id: UUID,
    topic: str | None,
    verdict: str,
    gate_verdict: str | None = None,
    score: float | None = None,
    reason: str | None = None,
    source_kind: str | None = None,
) -> MemoryEntry:
    """Record one verify/calib outcome as a trajectory entry (audit line).

    Not the mastery authority — ClaimRow is. ``source_kind`` is verify |
    calibration when known.
    """
    content: dict[str, Any] = {
        "claim_id": str(claim_id),
        "verdict": verdict,
        "gate_verdict": gate_verdict,
        "score": score,
        "reason": reason,
    }
    if source_kind:
        content["source"] = source_kind
    return await add_memory(
        session,
        user_id=user_id,
        layer="long",
        kind="trajectory",
        topic=topic,
        content=content,
        source={"claim_id": str(claim_id)},
    )


async def list_trajectory(
    session: AsyncSession,
    *,
    user_id: str,
    topic: str | None = None,
    claim_id: UUID | None = None,
    limit: int = 20,
) -> list[MemoryEntry]:
    """Prior verify outcomes, newest first. Filter by topic or claim_id."""
    stmt = select(MemoryEntryRow).where(
        MemoryEntryRow.user_id == user_id,
        MemoryEntryRow.kind == "trajectory",
    )
    if topic is not None:
        stmt = stmt.where(MemoryEntryRow.topic == topic)
    stmt = stmt.order_by(MemoryEntryRow.created_at.desc()).limit(limit)
    rows = list((await session.execute(stmt)).scalars().all())
    entries = [_memory_view(r) for r in rows]
    if claim_id is not None:
        entries = [e for e in entries if e.source.get("claim_id") == str(claim_id)]
    return entries


def count_prior_failures(trajectory: list[MemoryEntry], *, claim_id: UUID) -> int:
    """How many prior `owe_next` gate outcomes this claim has (SR weighting).

    Single source for schedule + due-sort fail severity (not fail_events).
    """
    key = str(claim_id)
    return sum(
        1
        for e in trajectory
        if e.source.get("claim_id") == key
        and (e.content.get("gate_verdict") or e.content.get("verdict")) == "owe_next"
    )


async def prior_failure_counts_by_claim(
    session: AsyncSession,
    *,
    user_id: str,
    claim_ids: list[UUID],
    limit: int = 200,
) -> dict[UUID, int]:
    """Map claim_id → owe_next count from trajectory (same rule as schedule)."""
    if not claim_ids:
        return {}
    wanted = {str(cid) for cid in claim_ids}
    entries = await list_memory(
        session, user_id=user_id, kind="trajectory", limit=limit
    )
    out: dict[UUID, int] = {cid: 0 for cid in claim_ids}
    for e in entries:
        raw = e.source.get("claim_id") or e.content.get("claim_id")
        if not isinstance(raw, str) or raw not in wanted:
            continue
        gate = e.content.get("gate_verdict") or e.content.get("verdict")
        if gate != "owe_next":
            continue
        try:
            cid = UUID(raw)
        except ValueError:
            continue
        out[cid] = out.get(cid, 0) + 1
    return out


async def maybe_record_failure_digest(
    session: AsyncSession,
    *,
    user_id: str,
    claim_id: UUID,
    claim_text: str,
    verdict: str,
    topic: str | None = None,
    follow_up: str | None = None,
    reason: str | None = None,
    source: str | None = None,
) -> MemoryEntry | None:
    """Derived cache: pending push + re-practice tip (not mastery authority).

    One row per (claim_id, verdict). If a row exists, fill empty follow_up/reason
    without resetting ``notified``. Returns None when nothing new was written.
    """
    if verdict not in {"almost", "owe_next"}:
        return None
    existing = await list_memory(
        session, user_id=user_id, kind="failure_digest", limit=100
    )
    key = str(claim_id)
    tip = (follow_up or "").strip()[:240] or None
    why = (reason or "").strip()[:240] or None
    for e in existing:
        if e.content.get("claim_id") != key or e.content.get("verdict") != verdict:
            continue
        row = await session.get(MemoryEntryRow, e.id)
        if row is None:
            return None
        content = dict(row.content or {})
        updated = False
        if tip and not content.get("follow_up"):
            content["follow_up"] = tip
            updated = True
        if why and not content.get("reason"):
            content["reason"] = why
            updated = True
        if source and not content.get("source"):
            content["source"] = source
            updated = True
        if not updated:
            return None
        row.content = content
        await session.flush()
        return _memory_view(row)
    content: dict[str, Any] = {
        "claim_id": key,
        "claim_text": (claim_text or "").strip()[:240],
        "verdict": verdict,
        "follow_up": tip,
        "reason": why,
        "notified": False,
    }
    if source:
        content["source"] = source
    return await add_memory(
        session,
        user_id=user_id,
        layer="working",
        kind="failure_digest",
        topic=topic,
        content=content,
        source={"claim_id": key, "skill": "failure-digest"},
    )


async def list_pending_failure_digests(
    session: AsyncSession,
    *,
    user_id: str,
    limit: int = 20,
) -> list[MemoryEntry]:
    entries = await list_memory(
        session, user_id=user_id, kind="failure_digest", limit=limit * 2
    )
    pending = [e for e in entries if not e.content.get("notified")]
    return pending[:limit]


async def mark_failure_digest_notified(
    session: AsyncSession,
    memory_id: UUID,
    *,
    user_id: str,
) -> MemoryEntry:
    row = await session.get(MemoryEntryRow, memory_id)
    if row is None or row.user_id != user_id or row.kind != "failure_digest":
        raise KeyError(f"failure_digest not found: {memory_id}")
    content = dict(row.content or {})
    content["notified"] = True
    row.content = content
    await session.flush()
    return _memory_view(row)


async def failure_hints_by_claim(
    session: AsyncSession,
    *,
    user_id: str,
    claim_ids: list[UUID],
    limit: int = 80,
) -> dict[UUID, str]:
    """Map claim_id → quiet DailyBrief tip from newest matching failure_digest."""
    from gotit.core.failure_lessons import brief_failure_hint

    if not claim_ids:
        return {}
    wanted = {str(cid) for cid in claim_ids}
    entries = await list_memory(
        session, user_id=user_id, kind="failure_digest", limit=limit
    )
    # Newest first from list_memory; keep first hit per claim.
    out: dict[UUID, str] = {}
    for e in entries:
        raw_id = e.content.get("claim_id")
        if not isinstance(raw_id, str) or raw_id not in wanted:
            continue
        try:
            cid = UUID(raw_id)
        except ValueError:
            continue
        if cid in out:
            continue
        verdict = e.content.get("verdict")
        if verdict not in {"almost", "owe_next"}:
            continue
        follow = e.content.get("follow_up")
        claim_text = e.content.get("claim_text")
        tip = brief_failure_hint(
            follow_up=str(follow) if follow else None,
            claim_text=str(claim_text) if claim_text else None,
        )
        if tip:
            out[cid] = tip
    return out


async def build_failure_lesson_block(
    session: AsyncSession,
    *,
    user_id: str,
    claim_id: UUID,
    topic: str | None = None,
    neighbor_claim_ids: list[UUID] | None = None,
) -> str | None:
    """Budgeted failure_digest excerpt for Axiom examine context; None if none match.

    Prefer same claim → confuse neighbors → same topic. Hard caps in
    ``gotit.core.failure_lessons``. Does not replace claim text.
    """
    from gotit.core.failure_lessons import (
        FAILURE_LESSON_FETCH_LIMIT,
        FailureLessonCandidate,
        budget_failure_lesson_block,
    )
    from gotit.core.mastery_graph import (
        BUDGET_CONFUSED_MAX,
        CONFUSED_THRESHOLD,
        pick_confused_neighbors,
    )
    from gotit.core.schedule import top_confuse_neighbor_ids
    from gotit.db.ops.graph import list_confused_edges

    neighbors = list(neighbor_claim_ids or [])
    edge_rows = await list_confused_edges(session, user_id=user_id, min_weight=1)
    edge_tuples = [
        (r.source_claim_id, r.target_claim_id, int(r.weight)) for r in edge_rows
    ]
    graph_neighbors = pick_confused_neighbors(
        target_id=claim_id,
        edges=edge_tuples,
        limit=BUDGET_CONFUSED_MAX,
        threshold=CONFUSED_THRESHOLD,
    )
    # Also pull top weight≥1 neighbor for re-practice lesson ranking.
    for nid in top_confuse_neighbor_ids(
        target_id=claim_id, edges=edge_tuples, limit=1, min_weight=1
    ):
        if nid not in graph_neighbors:
            graph_neighbors = [nid, *graph_neighbors][:BUDGET_CONFUSED_MAX]
    seen = {n for n in neighbors}
    for nid in graph_neighbors:
        if nid not in seen:
            neighbors.append(nid)
            seen.add(nid)

    entries = await list_memory(
        session,
        user_id=user_id,
        kind="failure_digest",
        limit=FAILURE_LESSON_FETCH_LIMIT,
    )
    candidates = [
        FailureLessonCandidate(
            claim_id=str(e.content.get("claim_id") or e.source.get("claim_id") or ""),
            verdict=str(e.content.get("verdict") or ""),
            claim_text=str(e.content.get("claim_text") or ""),
            follow_up=(
                str(e.content["follow_up"])
                if e.content.get("follow_up") is not None
                else None
            ),
            topic=e.topic,
            created_at=e.created_at,
        )
        for e in entries
    ]
    return budget_failure_lesson_block(
        candidates,
        claim_id=claim_id,
        neighbor_ids=neighbors,
        topic=topic,
    )


async def failure_writeback_and_lessons(
    session: AsyncSession,
    *,
    user_id: str,
    claim_id: UUID,
    claim_text: str,
    verdict: str,
    topic: str | None = None,
    follow_up: str | None = None,
    neighbor_claim_ids: list[UUID] | None = None,
) -> tuple[MemoryEntry | None, str | None]:
    """Harness-friendly round: digest write (deduped) → budgeted lesson block.

    Pure ops surface for eval cases — no REST/UI. ``digest`` is None when
    verdict is not almost/owe_next or (claim_id, verdict) already exists.
    """
    digest = await maybe_record_failure_digest(
        session,
        user_id=user_id,
        claim_id=claim_id,
        claim_text=claim_text,
        topic=topic,
        verdict=verdict,
        follow_up=follow_up,
    )
    block = await build_failure_lesson_block(
        session,
        user_id=user_id,
        claim_id=claim_id,
        topic=topic,
        neighbor_claim_ids=neighbor_claim_ids,
    )
    return digest, block
