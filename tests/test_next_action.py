"""State-driven next_action — pure routing, no Workflow Engine."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from gotit.core.models import CheckMode
from gotit.core.next_action import (
    NextActionClaimHint,
    NextActionState,
    next_action,
)


def _due(
    *,
    preferred: str | None = None,
    reason: str | None = None,
    project_id=None,
) -> NextActionClaimHint:
    return NextActionClaimHint(
        claim_id=uuid4(),
        preferred_check_mode=preferred,
        project_id=project_id,
        due_reason_code=reason,
        topic="redis",
        text="sample",
        status="queued",
    )


def test_due_examine_first_touch() -> None:
    state = NextActionState(
        as_of=date(2026, 8, 4),
        due_claims=[_due(reason=None)],
    )
    action = next_action(state)
    assert action is not None
    assert action.action == "examine"
    assert action.open_key == "open_examine"
    assert action.reason_code == "due_examine"


def test_due_review_for_almost() -> None:
    state = NextActionState(
        as_of=date(2026, 8, 4),
        due_claims=[_due(reason="almost_today")],
    )
    action = next_action(state)
    assert action is not None
    assert action.action == "review"
    assert action.workflow == "examine"
    assert action.open_key == "open_examine"


def test_due_teach_uses_route_for_claim() -> None:
    state = NextActionState(
        as_of=date(2026, 8, 4),
        due_claims=[_due(preferred=CheckMode.TEACH_BACK.value, reason="almost_today")],
    )
    action = next_action(state)
    assert action is not None
    assert action.action == "teach"
    assert action.open_key == "open_teach"
    assert action.cta_label == "回讲"


def test_due_beats_interview_and_calibrate() -> None:
    state = NextActionState(
        as_of=date(2026, 8, 4),
        due_claims=[_due(reason="owe_scheduled")],
        interview_drill_suggested=True,
        calibration_eligible=True,
        claim_count=5,
    )
    action = next_action(state)
    assert action is not None
    assert action.action == "review"
    assert action.reason_code == "due_review"


def test_interview_drill_when_no_due() -> None:
    state = NextActionState(
        as_of=date(2026, 8, 4),
        interview_drill_suggested=True,
        calibration_eligible=True,
        claim_count=3,
    )
    action = next_action(state)
    assert action is not None
    assert action.action == "drill"
    assert action.reason_code == "interview_drill"
    assert action.open_key == "open_drill"


def test_calibrate_cold_start() -> None:
    state = NextActionState(
        as_of=date(2026, 8, 4),
        calibration_eligible=True,
        claim_count=4,
        mastered_count=0,
    )
    action = next_action(state)
    assert action is not None
    assert action.action == "calibrate"
    assert action.workflow == "calibrate"


def test_ability_pending_review() -> None:
    weak_id = uuid4()
    state = NextActionState(
        as_of=date(2026, 8, 4),
        pending_review_total=2,
        weak_claims=[
            NextActionClaimHint(
                claim_id=weak_id,
                topic="kafka",
                status="in_progress",
                text="weak",
            )
        ],
        claim_count=3,
        mastered_count=1,
    )
    action = next_action(state)
    assert action is not None
    assert action.action == "review"
    assert action.claim_id == weak_id
    assert action.reason_code == "ability_review"


def test_idle_when_all_mastered() -> None:
    state = NextActionState(
        as_of=date(2026, 8, 4),
        claim_count=2,
        mastered_count=2,
    )
    assert next_action(state) is None


def test_pool_examine_when_unmastered_no_calibrate() -> None:
    state = NextActionState(
        as_of=date(2026, 8, 4),
        claim_count=3,
        mastered_count=1,
        calibration_eligible=False,
        weak_claims=[
            NextActionClaimHint(
                claim_id=uuid4(),
                topic="sql",
                status="not_yet",
                text="left",
            )
        ],
    )
    action = next_action(state)
    assert action is not None
    assert action.action == "examine"
    assert action.reason_code == "pool_examine"


@pytest.mark.asyncio
async def test_build_next_action_empty_is_idle() -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from gotit.db.models import Base
    from gotit.db.ops.next_action import build_next_action

    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        action = await build_next_action(
            session, user_id="next-empty", as_of=date(2026, 8, 4)
        )
        assert action is None
    await engine.dispose()
