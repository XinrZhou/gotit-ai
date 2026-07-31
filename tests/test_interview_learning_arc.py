"""Interview learning arc — today's brief interview_focus assembly."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from gotit.core.models import InterviewRampPrefs
from gotit.db import ops as day_ops
from gotit.db.models import Base, ProjectRow


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


async def _seed_project(session: AsyncSession, name: str = "支付网关") -> None:
    session.add(
        ProjectRow(
            id=uuid4(),
            user_id="local",
            name=name,
            role="后端",
            goal=None,
            tech_stack=["Python"],
            status="active",
        )
    )
    await session.flush()


@pytest.mark.asyncio
async def test_silent_has_no_interview_focus(session: AsyncSession) -> None:
    now = datetime(2026, 7, 31, 8, 0, tzinfo=UTC)
    await _seed_project(session)
    await day_ops.upsert_interview(
        session,
        company="FarCo",
        role_title="后端",
        scheduled_at=now + timedelta(hours=200),  # > 168h → silent
        user_id="local",
        round="tech_1",
    )
    today = await day_ops.get_today(
        session, now.date(), user_id="local", now=now
    )
    assert today.interview_focus is None


@pytest.mark.asyncio
async def test_warm_has_featured_interview_focus(session: AsyncSession) -> None:
    now = datetime(2026, 7, 31, 8, 0, tzinfo=UTC)
    await _seed_project(session, "订单中台")
    await day_ops.upsert_interview(
        session,
        company="WarmCo",
        role_title="后端",
        scheduled_at=now + timedelta(hours=48),  # warm
        user_id="local",
        round="tech_2",
    )
    today = await day_ops.get_today(
        session, now.date(), user_id="local", now=now
    )
    focus = today.interview_focus
    assert focus is not None
    assert focus.ramp_tier == "warm"
    assert focus.prominence == "featured"
    assert "订单中台" in focus.prompt
    assert "加油" not in focus.prompt
    assert focus.open_drill.get("action") == "open_drill"
    assert focus.open_drill.get("round") == "tech_2"
    assert focus.open_drill.get("project_name") == "订单中台"
    assert focus.company == "WarmCo"


@pytest.mark.asyncio
async def test_prefs_off_hides_interview_focus(session: AsyncSession) -> None:
    now = datetime(2026, 7, 31, 8, 0, tzinfo=UTC)
    await _seed_project(session)
    await day_ops.upsert_interview(
        session,
        company="OffCo",
        role_title="SRE",
        scheduled_at=now + timedelta(hours=36),
        user_id="local",
    )
    await day_ops.put_interview_ramp_prefs(
        session,
        InterviewRampPrefs(enabled=False, max_nudges_per_week=2),
        user_id="local",
    )
    today = await day_ops.get_today(
        session, now.date(), user_id="local", now=now
    )
    assert today.interview_focus is None


@pytest.mark.asyncio
async def test_light_is_quiet_prominence(session: AsyncSession) -> None:
    now = datetime(2026, 7, 31, 8, 0, tzinfo=UTC)
    await _seed_project(session, "缓存层")
    await day_ops.upsert_interview(
        session,
        company="LightCo",
        role_title="后端",
        scheduled_at=now + timedelta(hours=120),  # light
        user_id="local",
    )
    today = await day_ops.get_today(
        session, now.date(), user_id="local", now=now
    )
    focus = today.interview_focus
    assert focus is not None
    assert focus.ramp_tier == "light"
    assert focus.prominence == "quiet"
    assert "缓存层" in focus.prompt
