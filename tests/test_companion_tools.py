"""Companion builtin tools — whitelist ops + metadata trail."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from gotit.api.companion_tools import (
    COMPANION_TOOL_HINT,
    ToolCallRecorder,
    build_companion_tools,
)
from gotit.core.agents.runtime import build_chat_prompt
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
async def test_get_today_and_list_due_record_metadata(session: AsyncSession) -> None:
    day = date(2026, 7, 30)
    claim = ClaimRow(
        id=uuid4(),
        user_id="local",
        text="注意力机制把 Q 和 K 做点积。",
        status=MasteryStatus.QUEUED.value,
        next_review_at=day,
        topic="transformer",
    )
    session.add(claim)
    await session.flush()

    recorder = ToolCallRecorder()
    tools = build_companion_tools(session, user_id="local", day=day, recorder=recorder)
    get_today = _unwrap(tools, "get_today")
    list_due = _unwrap(tools, "list_due_claims")

    today = await get_today()
    assert today["due_count"] == 1
    assert today["due_claims"][0]["id"] == str(claim.id)

    due = await list_due()
    assert due["count"] == 1
    assert due["claims"][0]["text"].startswith("注意力")

    meta = recorder.as_metadata()
    assert len(meta) == 2
    assert meta[0]["name"] == "get_today" and meta[0]["ok"] is True
    assert meta[1]["name"] == "list_due_claims" and "欠账" in meta[1]["summary"]
    assert "args_digest" in meta[0]


@pytest.mark.asyncio
async def test_start_examine_puts_claim_on_plan(session: AsyncSession) -> None:
    day = date(2026, 7, 30)
    claim = ClaimRow(
        id=uuid4(),
        user_id="local",
        text="Softmax 把分数变成概率。",
        status=MasteryStatus.QUEUED.value,
        next_review_at=day,
    )
    session.add(claim)
    await session.flush()

    recorder = ToolCallRecorder()
    tools = build_companion_tools(session, user_id="local", day=day, recorder=recorder)
    start = _unwrap(tools, "start_examine")
    out = await start()
    assert out["ok"] is True
    assert out["action"] == "open_examine"
    assert out["claim_id"] == str(claim.id)
    assert out["plan_changed"] is True

    plan = await day_ops.get_plan(session, day, user_id="local")
    assert any(
        i.claim_id == claim.id and i.status == PlanItemStatus.IN_PROGRESS for i in plan.items
    )
    await session.refresh(claim)
    assert claim.status == MasteryStatus.IN_PROGRESS.value

    trail = recorder.as_metadata()
    assert trail[-1]["name"] == "start_examine" and trail[-1]["ok"] is True


@pytest.mark.asyncio
async def test_add_memory_and_failure_lessons(session: AsyncSession) -> None:
    day = date(2026, 7, 30)
    recorder = ToolCallRecorder()
    tools = build_companion_tools(session, user_id="local", day=day, recorder=recorder)
    add_mem = _unwrap(tools, "add_memory")
    get_lessons = _unwrap(tools, "get_failure_lessons")

    saved = await add_mem("下次别把 KV 搞反", topic="transformer")
    assert saved["ok"] is True
    entries = await day_ops.list_memory(
        session, user_id="local", layer="long", kind="note", limit=5
    )
    assert any("KV" in str(e.content.get("text")) for e in entries)

    empty = await add_mem("   ")
    assert empty["ok"] is False

    lessons = await get_lessons()
    assert lessons["count"] == 0
    names = [c["name"] for c in recorder.as_metadata()]
    assert "add_memory" in names and "get_failure_lessons" in names


def test_tool_hint_in_prompt() -> None:
    prompt = build_chat_prompt(
        user_text="今天欠什么",
        history=[],
        memory=[],
        display_name="章鱼哥",
        tool_hint=COMPANION_TOOL_HINT,
    )
    assert "get_today" in prompt
    assert "start_examine" in prompt


def test_tool_call_metadata_shape() -> None:
    rec = ToolCallRecorder()
    rec.record("get_today", args={"day": "2026-07-30"}, ok=True, summary="欠账 2 条")
    meta = rec.as_metadata()
    assert meta == [
        {
            "name": "get_today",
            "args_digest": '{"day": "2026-07-30"}',
            "ok": True,
            "summary": "欠账 2 条",
        }
    ]


def test_stub_metadata_omits_tool_calls() -> None:
    from gotit.api.chat_orchestrator import _agent_metadata, _stub_turn

    turn = _stub_turn("axiom", "今天欠什么", None)
    meta = _agent_metadata(turn, tool_calls=None)
    assert "tool_calls" not in meta
    assert "桩回复" in turn.text


@pytest.mark.asyncio
async def test_run_chat_function_model_invokes_list_due(
    session: AsyncSession,
) -> None:
    """PromptedOutput + whitelist: FunctionModel tool_call is executed + recorded."""
    import json as _json
    from datetime import UTC, datetime

    from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
    from pydantic_ai.models.function import AgentInfo, FunctionModel

    from gotit.core.agents.runtime import AgentContext, run_chat
    from gotit.core.models import AgentIdentity, MemoryEntry

    day = date(2026, 7, 30)
    claim = ClaimRow(
        id=uuid4(),
        user_id="local",
        text="能讲清 red-black tree 旋转",
        status=MasteryStatus.QUEUED.value,
        next_review_at=day,
    )
    session.add(claim)
    await session.flush()

    recorder = ToolCallRecorder()
    tools = build_companion_tools(session, user_id="local", day=day, recorder=recorder)
    step = {"n": 0}

    async def model_fn(messages: object, info: AgentInfo) -> ModelResponse:
        step["n"] += 1
        names = [t.name for t in (info.function_tools or [])]
        assert "list_due_claims" in names
        if step["n"] == 1:
            return ModelResponse(parts=[ToolCallPart(tool_name="list_due_claims", args={})])
        payload = {
            "thinking": "用工具查了欠账",
            "text": "今天还欠一条红黑树。",
            "handoff_to": None,
            "reason": None,
        }
        return ModelResponse(parts=[TextPart(_json.dumps(payload, ensure_ascii=False))])

    class _EmptyMem:
        async def list_memory(
            self,
            *,
            layer: str | None = None,
            kind: str | None = None,
            topic: str | None = None,
            limit: int = 50,
        ) -> list[MemoryEntry]:
            return []

    class _EmptyMsg:
        async def list_messages(self, *, limit: int = 50) -> list[object]:
            return []

    now = datetime.now(UTC)
    identity = AgentIdentity(
        id=uuid4(),
        agent_name="axiom",
        display_name="章鱼哥",
        personality="严格但克制",
        role="examiner",
        llm_config={},
        memory_scope={},
        prompt_version_id=None,
        created_at=now,
        updated_at=now,
    )
    ctx = AgentContext(
        identity=identity,
        rubric=None,
        memory=_EmptyMem(),
        messages=_EmptyMsg(),
    )
    turn = await run_chat(
        ctx,
        FunctionModel(model_fn),
        user_text="今天欠什么",
        tools=tools,
        tool_hint=COMPANION_TOOL_HINT,
    )
    assert "红黑树" in turn.text or "欠" in turn.text
    assert any(c.name == "list_due_claims" and c.ok for c in recorder.calls)
