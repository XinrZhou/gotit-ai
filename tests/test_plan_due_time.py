"""Tests for plan due_time helpers + persistence."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from gotit.core.plan_time import parse_time_hint, resolve_due_time
from gotit.db import ops as day_ops
from gotit.db.models import Base


def test_parse_time_hint_evening() -> None:
    assert parse_time_hint("晚上7点 刷动态规划") == "19:00"
    assert parse_time_hint("早上7点 健身") == "07:00"
    assert parse_time_hint("刷题", default="09:00") == "09:00"


def test_resolve_due_time_prefers_explicit() -> None:
    assert resolve_due_time(due_time="21:30", title="晚上7点 刷题") == "21:30"
    assert resolve_due_time(due_time=None, title="晚上7点 刷题") == "19:00"


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


@pytest.mark.asyncio
async def test_upsert_stores_due_time(session: AsyncSession) -> None:
    day = date(2026, 7, 30)
    item = await day_ops.upsert_plan_item(
        session, day, title="刷动态规划", due_time="19:00"
    )
    assert item.due_time == "19:00"
    inferred = await day_ops.upsert_plan_item(
        session, day, title="晚上8点 读论文"
    )
    assert inferred.due_time == "20:00"
