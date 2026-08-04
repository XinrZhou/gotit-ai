"""LearnerStateSnapshot derived projection (no LLM, no new authority tables)."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from gotit.core.learner_state import (
    assemble_learner_state,
    compute_context_fingerprint,
)
from gotit.core.models import MasteryStatus
from gotit.db.models import Base, ClaimRow
from gotit.db.ops.claim import write_mastery_outcome
from gotit.db.ops.learner_state import build_learner_state


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


def test_fingerprint_stable_for_same_inputs() -> None:
    a = uuid4()
    b = uuid4()
    day = date(2026, 8, 3)
    f1 = compute_context_fingerprint(
        as_of=day,
        owed_claim_ids=[a, b],
        lesson_claim_ids=[a],
        confusion_pairs=[(a, b, 2)],
        interview_lane="warm",
    )
    f2 = compute_context_fingerprint(
        as_of=day,
        owed_claim_ids=[b, a],
        lesson_claim_ids=[a],
        confusion_pairs=[(a, b, 2)],
        interview_lane="warm",
    )
    assert f1 == f2
    assert len(f1) == 16


def test_assemble_sets_fingerprint() -> None:
    from gotit.core.learner_state import OwedSummary

    snap = assemble_learner_state(
        as_of=date(2026, 8, 3),
        user_id="u",
        owed_summary=OwedSummary(due_count=0),
        weak_clusters=[],
        active_confusions=[],
        failure_lessons=[],
    )
    assert snap.context_fingerprint
    assert snap.user_id == "u"


@pytest.mark.asyncio
async def test_build_learner_state_owed_changes_after_pass(
    session: AsyncSession,
) -> None:
    user_id = "snap-user"
    as_of = date(2026, 8, 3)
    claim_id = uuid4()
    session.add(
        ClaimRow(
            id=claim_id,
            user_id=user_id,
            text="Snapshot owed claim",
            status=MasteryStatus.QUEUED.value,
            topic="snap",
            next_review_at=as_of,
        )
    )
    await session.flush()

    before = await build_learner_state(session, user_id=user_id, as_of=as_of)
    assert before.owed_summary.due_count >= 1
    assert claim_id in before.owed_summary.sample_claim_ids
    fp_before = before.context_fingerprint

    await write_mastery_outcome(
        session,
        claim_id,
        verdict="passed",
        source="harness",
        user_id=user_id,
        as_of=as_of,
    )
    after = await build_learner_state(session, user_id=user_id, as_of=as_of)
    assert claim_id not in after.owed_summary.sample_claim_ids
    # Fingerprint should move when owed set changes.
    assert after.context_fingerprint != fp_before or after.owed_summary.due_count < (
        before.owed_summary.due_count
    )
