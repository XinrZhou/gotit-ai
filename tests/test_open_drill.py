"""Tests for companion start_drill / open_drill prepare path."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from gotit.api.chat_orchestrator import _agent_metadata, _stub_turn
from gotit.api.companion_tools import ToolCallRecorder, build_companion_tools
from gotit.core.models import DrillRound, ProjectStatus
from gotit.db.models import Base, InterviewEventRow, ProjectRow, ResumeRow


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
async def test_start_drill_prepare_only(session: AsyncSession) -> None:
    session.add(
        ResumeRow(
            id=uuid4(),
            user_id="local",
            upload_id=uuid4(),
            file_path="/tmp/r.pdf",
            document={"basics": {"name": "A"}},
        )
    )
    pid = uuid4()
    session.add(
        ProjectRow(
            id=pid,
            user_id="local",
            name="支付网关",
            status=ProjectStatus.ACTIVE.value,
        )
    )
    await session.flush()

    recorder = ToolCallRecorder()
    tools = build_companion_tools(
        session, user_id="local", day=date(2026, 7, 31), recorder=recorder
    )
    start = _unwrap(tools, "start_drill")
    out = await start(round="tech_2")
    assert out["ok"] is True
    assert out["action"] == "open_drill"
    assert out["round"] == DrillRound.TECH_2.value
    assert out["project_id"] == str(pid)
    assert out["has_resume"] is True

    trail = recorder.as_metadata()
    assert trail[-1]["name"] == "start_drill"
    assert trail[-1]["open_drill"]["round"] == "tech_2"
    # No drill session created
    from gotit.db import ops as day_ops

    sessions = await day_ops.list_drill_sessions(session, user_id="local")
    assert sessions == []


@pytest.mark.asyncio
async def test_start_drill_from_interview(session: AsyncSession) -> None:
    iid = uuid4()
    session.add(
        InterviewEventRow(
            id=iid,
            user_id="local",
            company="Acme",
            role_title="后端",
            scheduled_at=datetime.now(UTC) + timedelta(days=2),
            round="tech_3",
            status="scheduled",
            remind_offsets_hours=[-24, -2],
        )
    )
    await session.flush()

    recorder = ToolCallRecorder()
    tools = build_companion_tools(
        session, user_id="local", day=date(2026, 7, 31), recorder=recorder
    )
    start = _unwrap(tools, "start_drill")
    out = await start(interview_id=str(iid))
    assert out["ok"] is True
    assert out["round"] == "tech_3"
    assert out["company"] == "Acme"
    assert out["has_resume"] is False


def test_agent_metadata_lifts_open_drill() -> None:
    turn = _stub_turn("sage", "帮我深挖", None)
    tool_calls: list[dict[str, object]] = [
        {
            "name": "start_drill",
            "args_digest": "{}",
            "ok": True,
            "summary": "可深挖",
            "open_drill": {
                "action": "open_drill",
                "round": "tech_1",
                "has_resume": True,
            },
        },
    ]
    meta = _agent_metadata(turn, tool_calls=tool_calls)
    assert meta["open_drill"] == tool_calls[0]["open_drill"]
