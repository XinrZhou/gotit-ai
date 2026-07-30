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
) -> MemoryEntry:
    """Record one verify-loop outcome as a trajectory entry for the claim/topic.

    The next time the same topic/claim is examined, the examiner can read this to
    recall the learner's prior failure mode — turning verification from a
    one-shot event into a learning trajectory.
    """
    return await add_memory(
        session,
        user_id=user_id,
        layer="long",
        kind="trajectory",
        topic=topic,
        content={
            "claim_id": str(claim_id),
            "verdict": verdict,
            "gate_verdict": gate_verdict,
            "score": score,
            "reason": reason,
        },
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
    """How many prior `owe_next` outcomes this claim has (for SR interval weighting)."""
    key = str(claim_id)
    return sum(
        1
        for e in trajectory
        if e.source.get("claim_id") == key
        and (e.content.get("gate_verdict") or e.content.get("verdict")) == "owe_next"
    )


async def maybe_record_failure_digest(
    session: AsyncSession,
    *,
    user_id: str,
    claim_id: UUID,
    claim_text: str,
    verdict: str,
    topic: str | None = None,
    follow_up: str | None = None,
) -> MemoryEntry | None:
    """Queue a WeChat failure digest once per (claim_id, verdict). Returns None if dup."""
    if verdict not in {"almost", "owe_next"}:
        return None
    existing = await list_memory(
        session, user_id=user_id, kind="failure_digest", limit=100
    )
    key = str(claim_id)
    for e in existing:
        if e.content.get("claim_id") == key and e.content.get("verdict") == verdict:
            return None
    return await add_memory(
        session,
        user_id=user_id,
        layer="working",
        kind="failure_digest",
        topic=topic,
        content={
            "claim_id": key,
            "claim_text": (claim_text or "").strip()[:240],
            "verdict": verdict,
            "follow_up": (follow_up or "").strip()[:240] or None,
            "notified": False,
        },
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
