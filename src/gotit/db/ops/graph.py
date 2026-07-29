"""Mastery graph: fail events, confused_with edges, budget subgraph."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from gotit.core.mastery_graph import (
    BUDGET_CONFUSED_MAX,
    BUDGET_FAIL_REASONS_MAX,
    CONFUSED_THRESHOLD,
    FAIL_VERDICTS,
    canonical_claim_pair,
    format_budget_block,
    pick_confused_neighbors,
)
from gotit.core.models import BudgetSubgraphView, FailEventView
from gotit.db.models import ClaimRow, FailEventRow, GraphEdgeRow
from gotit.db.ops._common import DEFAULT_USER_ID


def _fail_view(row: FailEventRow) -> FailEventView:
    return FailEventView(
        id=row.id,
        claim_id=row.claim_id,
        topic=row.topic,
        gate_verdict=row.gate_verdict,
        score=row.score,
        reason=row.reason,
        created_at=row.created_at,
    )


async def record_fail_event(
    session: AsyncSession,
    *,
    user_id: str,
    claim_id: UUID,
    topic: str | None,
    gate_verdict: str,
    score: float | None = None,
    reason: str | None = None,
) -> FailEventView | None:
    """Persist a fail event when gate verdict is almost|owe_next; else no-op."""
    if gate_verdict not in FAIL_VERDICTS:
        return None
    row = FailEventRow(
        id=uuid4(),
        user_id=user_id,
        claim_id=claim_id,
        topic=topic,
        gate_verdict=gate_verdict,
        score=score,
        reason=reason,
        created_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()
    return _fail_view(row)


async def _topic_claims_with_fails(
    session: AsyncSession,
    *,
    user_id: str,
    topic: str,
    exclude_claim_id: UUID,
) -> list[UUID]:
    """Other same-topic claims that already have at least one fail_event."""
    stmt = (
        select(FailEventRow.claim_id)
        .where(
            FailEventRow.user_id == user_id,
            FailEventRow.topic == topic,
            FailEventRow.claim_id != exclude_claim_id,
        )
        .distinct()
    )
    return list((await session.execute(stmt)).scalars().all())


async def increment_confused_with(
    session: AsyncSession,
    *,
    user_id: str,
    claim_a: UUID,
    claim_b: UUID,
) -> GraphEdgeRow:
    src, tgt = canonical_claim_pair(claim_a, claim_b)
    stmt = select(GraphEdgeRow).where(
        GraphEdgeRow.user_id == user_id,
        GraphEdgeRow.source_claim_id == src,
        GraphEdgeRow.target_claim_id == tgt,
        GraphEdgeRow.rel == "confused_with",
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        row = GraphEdgeRow(
            id=uuid4(),
            user_id=user_id,
            source_claim_id=src,
            target_claim_id=tgt,
            rel="confused_with",
            weight=1,
            updated_at=datetime.now(UTC),
        )
        session.add(row)
    else:
        row.weight = int(row.weight) + 1
        row.updated_at = datetime.now(UTC)
    await session.flush()
    return row


async def grow_confused_edges_for_fail(
    session: AsyncSession,
    *,
    user_id: str,
    claim_id: UUID,
    topic: str | None,
) -> int:
    """Link failed claim to same-topic peers that already failed. Returns edge updates."""
    if not topic or not topic.strip():
        return 0
    peers = await _topic_claims_with_fails(
        session, user_id=user_id, topic=topic.strip(), exclude_claim_id=claim_id
    )
    n = 0
    for peer in peers:
        await increment_confused_with(
            session, user_id=user_id, claim_a=claim_id, claim_b=peer
        )
        n += 1
    return n


async def record_verify_mastery_writeback(
    session: AsyncSession,
    *,
    user_id: str,
    claim_id: UUID,
    topic: str | None,
    gate_verdict: str,
    score: float | None = None,
    reason: str | None = None,
) -> dict[str, object]:
    """Gate writeback: fail event + confused_with growth when not passed."""
    event = await record_fail_event(
        session,
        user_id=user_id,
        claim_id=claim_id,
        topic=topic,
        gate_verdict=gate_verdict,
        score=score,
        reason=reason,
    )
    grown = 0
    if event is not None:
        grown = await grow_confused_edges_for_fail(
            session, user_id=user_id, claim_id=claim_id, topic=topic
        )
    return {
        "fail_event": event.model_dump(mode="json") if event else None,
        "confused_edges_touched": grown,
    }


async def list_confused_edges(
    session: AsyncSession,
    *,
    user_id: str = DEFAULT_USER_ID,
    min_weight: int = 1,
) -> list[GraphEdgeRow]:
    stmt = select(GraphEdgeRow).where(
        GraphEdgeRow.user_id == user_id,
        GraphEdgeRow.rel == "confused_with",
        GraphEdgeRow.weight >= min_weight,
    )
    return list((await session.execute(stmt)).scalars().all())


async def fail_counts_by_claim(
    session: AsyncSession,
    *,
    user_id: str,
    claim_ids: list[UUID] | None = None,
) -> dict[UUID, int]:
    stmt = (
        select(FailEventRow.claim_id, func.count())
        .where(FailEventRow.user_id == user_id)
        .group_by(FailEventRow.claim_id)
    )
    if claim_ids is not None:
        if not claim_ids:
            return {}
        stmt = stmt.where(FailEventRow.claim_id.in_(claim_ids))
    rows = (await session.execute(stmt)).all()
    return {cid: int(n) for cid, n in rows}


async def build_budget_subgraph(
    session: AsyncSession,
    *,
    user_id: str,
    claim_id: UUID,
) -> BudgetSubgraphView:
    edge_rows = await list_confused_edges(session, user_id=user_id, min_weight=1)
    tuples = [
        (r.source_claim_id, r.target_claim_id, int(r.weight)) for r in edge_rows
    ]
    neighbor_ids = pick_confused_neighbors(
        target_id=claim_id,
        edges=tuples,
        limit=BUDGET_CONFUSED_MAX,
        threshold=CONFUSED_THRESHOLD,
    )
    labels: list[str] = []
    if neighbor_ids:
        claims = list(
            (
                await session.execute(
                    select(ClaimRow).where(
                        ClaimRow.id.in_(neighbor_ids), ClaimRow.user_id == user_id
                    )
                )
            )
            .scalars()
            .all()
        )
        by_id = {c.id: c for c in claims}
        for nid in neighbor_ids:
            c = by_id.get(nid)
            if c is not None:
                labels.append(c.text[:200])

    fail_stmt = (
        select(FailEventRow)
        .where(FailEventRow.user_id == user_id, FailEventRow.claim_id == claim_id)
        .order_by(FailEventRow.created_at.desc())
        .limit(BUDGET_FAIL_REASONS_MAX)
    )
    fails = list((await session.execute(fail_stmt)).scalars().all())
    reasons = [
        (f.reason or f.gate_verdict).strip()
        for f in fails
        if (f.reason or f.gate_verdict)
    ]

    block = format_budget_block(confused_labels=labels, fail_reasons=reasons)
    return BudgetSubgraphView(
        claim_id=claim_id,
        confused_claim_ids=neighbor_ids,
        confused_labels=labels,
        fail_reasons=reasons,
        prompt_block=block,
    )
