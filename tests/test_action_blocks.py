"""Chat metadata.action_blocks — owed / verdict helpers + companion fill."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from gotit.api.action_blocks import (
    ACTION_BLOCKS_CAP,
    attach_verdict_blocks,
    collect_action_blocks,
    owed_blocks_from_claims,
    verdict_block,
)
from gotit.api.chat_orchestrator import _agent_metadata, _stub_turn
from gotit.api.companion_tools import ToolCallRecorder, build_companion_tools
from gotit.core.models import MasteryStatus
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


def test_owed_and_verdict_block_shape() -> None:
    owed = owed_blocks_from_claims(
        [
            {
                "id": "c1",
                "text": "注意力把 Q 和 K 做点积。",
                "due_reason_text": "今天到期",
            }
        ]
    )
    assert len(owed) == 1
    assert owed[0]["type"] == "owed_claim"
    assert owed[0]["claim_id"] == "c1"
    assert owed[0]["actions"] == [{"id": "start_examine", "label": "开考"}]
    assert owed[0]["due_reason_text"] == "今天到期"

    almost = verdict_block(gate_verdict="almost", claim_id="c1")
    assert almost["type"] == "verdict"
    assert almost["actions"] == [{"id": "start_examine", "label": "再练"}]

    passed = verdict_block(gate_verdict="passed", claim_id="c1")
    assert passed["actions"] == []


def test_action_blocks_cap_and_collect() -> None:
    many = owed_blocks_from_claims([{"id": f"c{i}", "text": f"claim {i}"} for i in range(12)])
    assert len(many) == ACTION_BLOCKS_CAP

    trail = [
        {"ok": True, "action_blocks": many},
        {"ok": False, "action_blocks": [{"type": "owed_claim", "claim_id": "x"}]},
    ]
    merged = collect_action_blocks(trail)
    assert len(merged) == ACTION_BLOCKS_CAP


def test_agent_metadata_lifts_action_blocks() -> None:
    turn = _stub_turn("axiom", "hi", None)
    blocks = owed_blocks_from_claims([{"id": "c1", "text": "Q·K"}])
    tool_calls: list[dict[str, object]] = [
        {
            "name": "list_due_claims",
            "args_digest": "{}",
            "ok": True,
            "summary": "欠账 1 条",
            "action_blocks": blocks,
        }
    ]
    meta = _agent_metadata(turn, tool_calls=tool_calls)
    assert meta["action_blocks"] == blocks


def test_attach_verdict_blocks() -> None:
    meta: dict[str, object] = {"verdict": "almost"}
    attach_verdict_blocks(meta, gate_verdict="almost", claim_id="c9")
    assert meta["action_blocks"][0]["type"] == "verdict"  # type: ignore[index]
    assert meta["action_blocks"][0]["actions"][0]["label"] == "再练"  # type: ignore[index]


@pytest.mark.asyncio
async def test_list_due_claims_fills_action_blocks(session: AsyncSession) -> None:
    day = date(2026, 7, 30)
    claim = ClaimRow(
        id=uuid4(),
        user_id="local",
        text="Softmax 把分数变成概率。",
        status=MasteryStatus.QUEUED.value,
        next_review_at=day,
        topic="transformer",
    )
    session.add(claim)
    await session.flush()

    recorder = ToolCallRecorder()
    tools = build_companion_tools(session, user_id="local", day=day, recorder=recorder)
    list_due = _unwrap(tools, "list_due_claims")
    due = await list_due()
    assert due["count"] == 1
    assert due["action_blocks"][0]["type"] == "owed_claim"
    assert due["action_blocks"][0]["claim_id"] == str(claim.id)
    assert due["action_blocks"][0]["actions"][0]["id"] == "start_examine"

    trail = recorder.as_metadata()
    assert trail[-1]["action_blocks"][0]["claim_id"] == str(claim.id)
