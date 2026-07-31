"""Day close ritual — suggest / close / idempotent."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from gotit.api.companion_tools import ToolCallRecorder, build_companion_tools
from gotit.core.models import MasteryStatus, PlanItemStatus
from gotit.db import ops as day_ops
from gotit.db.models import Base, ClaimRow


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


def _unwrap(tools: list[object], name: str):
    for t in tools:
        fn = getattr(t, "function", None) or t
        if getattr(fn, "__name__", None) == name:
            return fn
        if getattr(t, "name", None) == name:
            return fn
    raise KeyError(name)


@pytest.mark.asyncio
async def test_close_suggested_when_owed_clear(session: AsyncSession) -> None:
    day = date(2026, 7, 31)
    today = await day_ops.get_today(session, day, user_id="local")
    assert today.day_closed is False
    assert today.close_suggested is True
    assert today.close_summary is None

    claim = ClaimRow(
        id=uuid4(),
        user_id="local",
        text="欠着的一条",
        status=MasteryStatus.QUEUED.value,
        next_review_at=day,
    )
    session.add(claim)
    await session.flush()
    owed = await day_ops.get_today(session, day, user_id="local")
    assert owed.close_suggested is False
    assert len(owed.due_claims) == 1


@pytest.mark.asyncio
async def test_close_today_idempotent_and_summary(session: AsyncSession) -> None:
    day = date(2026, 7, 31)
    claim = ClaimRow(
        id=uuid4(),
        user_id="local",
        text="已过的一条",
        status=MasteryStatus.MASTERED.value,
        next_review_at=None,
    )
    session.add(claim)
    await session.flush()
    await day_ops.upsert_plan_item(
        session,
        day,
        title=claim.text,
        user_id="local",
        claim_id=claim.id,
        status=PlanItemStatus.VERIFIED,
    )
    owed = ClaimRow(
        id=uuid4(),
        user_id="local",
        text="还挂着",
        status=MasteryStatus.QUEUED.value,
        next_review_at=day,
    )
    session.add(owed)
    await session.flush()

    first = await day_ops.close_today(session, day, user_id="local")
    assert first.passed_count == 1
    assert first.still_owed_count == 1
    assert "还挂" in first.note
    assert first.closed_at is not None

    second = await day_ops.close_today(
        session, day, user_id="local", note="should not overwrite"
    )
    assert second.closed_at == first.closed_at
    assert second.note == first.note
    assert second.passed_count == first.passed_count

    today = await day_ops.get_today(session, day, user_id="local")
    assert today.day_closed is True
    assert today.close_summary is not None
    assert today.close_summary.passed_count == 1
    assert today.close_summary.still_owed_count == 1


@pytest.mark.asyncio
async def test_api_close_today(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    day = "2026-07-31"
    r = await client.post(
        "/v1/days/today/close",
        headers=auth_headers,
        params={"day": day},
        json={"note": "先停一下"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["note"] == "先停一下"
    assert body["closed_at"] is not None

    r2 = await client.post(
        "/v1/days/today/close",
        headers=auth_headers,
        params={"day": day},
        json={"note": "ignored"},
    )
    assert r2.status_code == 200
    assert r2.json()["note"] == "先停一下"

    today = await client.get("/v1/today", headers=auth_headers, params={"day": day})
    assert today.status_code == 200
    snap = today.json()
    assert snap["day_closed"] is True
    assert snap["close_summary"]["note"] == "先停一下"


@pytest.mark.asyncio
async def test_companion_close_day(session: AsyncSession) -> None:
    day = date(2026, 7, 31)
    recorder = ToolCallRecorder()
    tools = build_companion_tools(session, user_id="local", day=day, recorder=recorder)
    close = _unwrap(tools, "close_day")
    out = await close()
    assert out["ok"] is True
    assert out["still_owed_count"] == 0
    trail = recorder.as_metadata()
    assert trail[-1]["name"] == "close_day" and trail[-1]["ok"] is True
    assert "收工" in trail[-1]["summary"] or "过了" in trail[-1]["summary"]
