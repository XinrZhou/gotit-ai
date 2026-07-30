"""Pin spaced-review formula + due sort / confuse helpers."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from gotit.core.models import MasteryStatus
from gotit.core.schedule import (
    MAX_INTERVAL_DAYS,
    compute_next_review,
    confuse_weights_from_edges,
    due_sort_key,
    explain_due_reason,
    owe_interval_days,
    schedule_after_verdict,
    top_confuse_neighbor_ids,
)
from gotit.db import ops as day_ops
from gotit.db.models import Base, ClaimRow, GraphEdgeRow


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as sess:
        yield sess
        await sess.commit()
    await engine.dispose()


def test_owe_interval_formula() -> None:
    assert owe_interval_days(0) == 1
    assert owe_interval_days(1) == 3
    assert owe_interval_days(2) == 5
    assert owe_interval_days(100) == MAX_INTERVAL_DAYS


def test_compute_next_review_verdicts() -> None:
    day = date(2026, 7, 30)
    passed = compute_next_review("passed", as_of=day, prior_failures=3)
    assert passed.next_review_at is None
    assert passed.reason_code == "passed_clear"

    almost = compute_next_review("almost", as_of=day, prior_failures=9)
    assert almost.next_review_at == day
    assert almost.reason_code == "almost_today"
    assert almost.interval_days == 0

    owe0 = compute_next_review("owe_next", as_of=day, prior_failures=0)
    assert owe0.next_review_at == day + timedelta(days=1)
    assert owe0.reason_code == "owe_scheduled"
    assert owe0.interval_days == 1

    owe1 = schedule_after_verdict("owe_next", prior_failures=1, as_of=day)
    assert owe1.next_review_at == day + timedelta(days=3)
    assert owe1.interval_days == 3


def test_due_sort_overdue_before_confuse() -> None:
    day = date(2026, 7, 30)
    a = uuid4()
    b = uuid4()
    c = uuid4()
    # a overdue 5d, b due today with high fails+confuse, c null review (very overdue)
    keys = [
        (
            due_sort_key(
                as_of=day,
                next_review_at=day - timedelta(days=5),
                fail_count=0,
                confuse_weight=0,
                claim_id=a,
            ),
            a,
        ),
        (
            due_sort_key(
                as_of=day,
                next_review_at=day,
                fail_count=10,
                confuse_weight=9,
                claim_id=b,
            ),
            b,
        ),
        (
            due_sort_key(
                as_of=day,
                next_review_at=None,
                fail_count=0,
                confuse_weight=0,
                claim_id=c,
            ),
            c,
        ),
    ]
    ordered = [cid for _, cid in sorted(keys, key=lambda t: t[0])]
    assert ordered[0] == c  # null review sorts first
    assert ordered[1] == a  # then overdue
    assert ordered[2] == b


def test_confuse_weights_and_neighbors() -> None:
    a, b, c = uuid4(), uuid4(), uuid4()
    edges = [(a, b, 5), (a, c, 2)]
    weights = confuse_weights_from_edges([a, b, c], edges)
    assert weights[a] == 5
    assert weights[b] == 5
    assert weights[c] == 2
    tops = top_confuse_neighbor_ids(target_id=a, edges=edges, limit=1)
    assert tops == [b]


def test_explain_due_reason_codes() -> None:
    day = date(2026, 7, 30)
    code, text = explain_due_reason(
        as_of=day,
        status="in_progress",
        next_review_at=day,
    )
    assert code == "almost_today"
    assert "还差点" in text or "接着" in text

    code, text = explain_due_reason(
        as_of=day,
        status="queued",
        next_review_at=day - timedelta(days=2),
    )
    assert code == "overdue"
    assert "2" in text

    code, text = explain_due_reason(
        as_of=day,
        status="queued",
        next_review_at=None,
        confuse_weight=3,
        confuse_neighbor_label="pointer vs array",
    )
    assert code == "confuse_boost"
    assert "pointer" in text


@pytest.mark.asyncio
async def test_apply_examine_verdict_uses_schedule(session: AsyncSession) -> None:
    day = date(2026, 7, 30)
    claim = day_ops.stub_extract_claim("Schedule writeback pins interval.")
    session.add(
        ClaimRow(
            id=claim.id,
            user_id="local",
            text=claim.text,
            source_excerpt=claim.source_excerpt,
            status=MasteryStatus.NOT_YET.value,
        )
    )
    await session.flush()

    almost = await day_ops.apply_examine_verdict(
        session, claim.id, verdict="almost", as_of=day
    )
    assert almost["schedule_reason"] == "almost_today"
    assert almost["claim"]["next_review_at"] == day.isoformat()
    assert almost["claim"]["status"] == MasteryStatus.IN_PROGRESS.value

    owe = await day_ops.apply_examine_verdict(
        session, claim.id, verdict="owe_next", as_of=day, prior_failures=2
    )
    assert owe["schedule_reason"] == "owe_scheduled"
    assert owe["interval_days"] == 5
    assert owe["claim"]["next_review_at"] == (day + timedelta(days=5)).isoformat()

    passed = await day_ops.apply_examine_verdict(
        session, claim.id, verdict="passed", as_of=day
    )
    assert passed["schedule_reason"] == "passed_clear"
    assert passed["claim"]["next_review_at"] is None


@pytest.mark.asyncio
async def test_due_sort_prefers_confuse_when_equal_overdue(
    session: AsyncSession,
) -> None:
    day = date(2026, 7, 30)
    low = uuid4()
    high = uuid4()
    peer = uuid4()
    # Canonical order for undirected edge endpoints.
    src, tgt = (high, peer) if str(high) <= str(peer) else (peer, high)
    session.add_all(
        [
            ClaimRow(
                id=low,
                user_id="local",
                text="low confuse",
                status=MasteryStatus.QUEUED.value,
                next_review_at=day,
            ),
            ClaimRow(
                id=high,
                user_id="local",
                text="high confuse",
                status=MasteryStatus.QUEUED.value,
                next_review_at=day,
            ),
            ClaimRow(
                id=peer,
                user_id="local",
                text="peer (not due)",
                status=MasteryStatus.MASTERED.value,
                next_review_at=None,
            ),
            GraphEdgeRow(
                id=uuid4(),
                user_id="local",
                source_claim_id=src,
                target_claim_id=tgt,
                rel="confused_with",
                weight=4,
            ),
        ]
    )
    await session.flush()

    due = await day_ops.list_due_claims(session, day, user_id="local")
    ids = [c.id for c in due]
    assert high in ids and low in ids
    assert ids.index(high) < ids.index(low)

    today = await day_ops.get_today(session, day, user_id="local")
    by_id = {c.id: c for c in today.due_claims}
    assert by_id[high].due_reason_code == "confuse_boost"
    assert by_id[high].due_reason_text
    assert by_id[low].due_reason_code == "owe_scheduled"