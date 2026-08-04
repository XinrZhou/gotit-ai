"""Ability State Projection — derived read model (no Ability table, no mastery write)."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from gotit.core.ability_projection import (
    AbilityClaimInput,
    AbilityTrajectoryInput,
    assemble_ability_state,
    compute_recent_trend,
    topic_key,
)
from gotit.core.models import MasteryStatus
from gotit.db.models import Base, ClaimRow
from gotit.db.ops.ability_projection import build_ability_state
from gotit.db.ops.claim import write_mastery_outcome
from gotit.db.ops.memory import append_trajectory


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


def test_topic_key_untagged() -> None:
    assert topic_key(None) == "(untagged)"
    assert topic_key("  ") == "(untagged)"
    assert topic_key(" Redis ") == "Redis"


def test_compute_recent_trend() -> None:
    assert compute_recent_trend([]) == "unknown"
    assert compute_recent_trend(["passed", "passed", "almost"]) == "improving"
    assert compute_recent_trend(["owe_next", "owe_next", "almost"]) == "declining"
    assert compute_recent_trend(["passed", "owe_next"]) == "stable"


def test_assemble_ability_state_counts_and_weak_points() -> None:
    as_of = date(2026, 8, 4)
    mastered_id = uuid4()
    weak_id = uuid4()
    due_id = uuid4()
    proj = assemble_ability_state(
        as_of=as_of,
        user_id="u",
        claims=[
            AbilityClaimInput(
                id=mastered_id,
                text="Mastered claim",
                topic="redis",
                status="mastered",
                next_review_at=None,
            ),
            AbilityClaimInput(
                id=weak_id,
                text="Weak claim about eviction",
                topic="redis",
                status="in_progress",
                next_review_at=as_of,
            ),
            AbilityClaimInput(
                id=due_id,
                text="Queued for review",
                topic="redis",
                status="queued",
                next_review_at=as_of - timedelta(days=1),
            ),
            AbilityClaimInput(
                id=uuid4(),
                text="Other topic",
                topic="postgres",
                status="not_yet",
                next_review_at=None,
            ),
        ],
        trajectory=[
            AbilityTrajectoryInput(
                claim_id=mastered_id,
                topic="redis",
                gate_verdict="passed",
            ),
            AbilityTrajectoryInput(
                claim_id=weak_id,
                topic="redis",
                gate_verdict="almost",
                reason="missed TTL edge",
            ),
            AbilityTrajectoryInput(
                claim_id=due_id,
                topic="redis",
                gate_verdict="owe_next",
            ),
        ],
        fail_hints={weak_id: "missed TTL edge"},
    )
    redis = next(a for a in proj.abilities if a.ability == "redis")
    assert redis.claim_count == 3
    assert redis.mastered_count == 1
    assert redis.verified_count == 1
    assert redis.pending_review == 2
    assert redis.trajectory_passes == 1
    assert redis.trajectory_failures == 2
    assert redis.recent_trend in {"stable", "declining", "improving"}
    assert any(w.claim_id == weak_id and w.fail_hint for w in redis.weak_points)
    assert "write_mastery" not in repr(proj)


@pytest.mark.asyncio
async def test_build_ability_state_after_pass(session: AsyncSession) -> None:
    user_id = "ability-user"
    as_of = date(2026, 8, 4)
    claim_id = uuid4()
    session.add(
        ClaimRow(
            id=claim_id,
            user_id=user_id,
            text="Ability projection claim",
            status=MasteryStatus.QUEUED.value,
            topic="kafka",
            next_review_at=as_of,
        )
    )
    await session.flush()
    await append_trajectory(
        session,
        user_id=user_id,
        claim_id=claim_id,
        topic="kafka",
        verdict="owe_next",
        gate_verdict="owe_next",
        source_kind="verify",
    )

    before = await build_ability_state(session, user_id=user_id, as_of=as_of)
    kafka = next(a for a in before.abilities if a.ability == "kafka")
    assert kafka.mastered_count == 0
    assert kafka.pending_review >= 1
    assert kafka.trajectory_failures >= 1

    await write_mastery_outcome(
        session,
        claim_id,
        verdict="passed",
        source="harness",
        user_id=user_id,
        as_of=as_of,
    )
    await append_trajectory(
        session,
        user_id=user_id,
        claim_id=claim_id,
        topic="kafka",
        verdict="passed",
        gate_verdict="passed",
        source_kind="verify",
    )

    after = await build_ability_state(session, user_id=user_id, as_of=as_of)
    kafka2 = next(a for a in after.abilities if a.ability == "kafka")
    assert kafka2.mastered_count == 1
    assert kafka2.verified_count == 1
    assert kafka2.pending_review == 0
    assert kafka2.trajectory_passes >= 1
