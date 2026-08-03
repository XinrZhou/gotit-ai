"""Budgeted failure_digest → Axiom examine context."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from gotit.core.agents.axiom import build_prompt, build_topic_prompt
from gotit.core.agents.echo import build_prompt as build_echo_prompt
from gotit.core.context_budget import DEFAULT_CONTEXT_BUDGET
from gotit.core.failure_lessons import (
    FAILURE_LESSON_MAX_CHARS,
    FAILURE_LESSON_MAX_ITEMS,
    FailureLessonCandidate,
    brief_failure_hint,
    budget_failure_lesson_block,
    format_failure_lesson_block,
    learner_failure_hint,
    select_failure_lessons,
)
from gotit.core.models import MasteryStatus, PlanItemSource
from gotit.db.models import Base, ClaimRow, LearningDayRow, MemoryEntryRow, PlanItemRow
from gotit.db.ops import claim as claim_ops
from gotit.db.ops import memory as memory_ops


def _cand(
    *,
    claim_id: str,
    verdict: str = "owe_next",
    claim_text: str = "claim text",
    follow_up: str | None = "missed Q/K/V",
    topic: str | None = "transformers",
    hours_ago: int = 0,
) -> FailureLessonCandidate:
    return FailureLessonCandidate(
        claim_id=claim_id,
        verdict=verdict,
        claim_text=claim_text,
        follow_up=follow_up,
        topic=topic,
        created_at=datetime.now(UTC) - timedelta(hours=hours_ago),
    )


def test_learner_failure_hint_from_block() -> None:
    cid = uuid4()
    block = format_failure_lesson_block(
        [
            _cand(
                claim_id=str(cid),
                follow_up="Q/K/V 搞混了",
            )
        ],
        claim_id=cid,
    )
    hint = learner_failure_hint(block)
    assert hint is not None
    assert hint.startswith("你曾在这栽过：")
    assert "Q/K/V" in hint
    assert learner_failure_hint(None) is None
    assert learner_failure_hint("") is None


def test_brief_failure_hint() -> None:
    assert brief_failure_hint(follow_up="漏了边界条件") == "曾栽过：漏了边界条件"
    assert brief_failure_hint(follow_up=None, claim_text="claim only") == (
        "曾栽过：claim only"
    )
    assert brief_failure_hint(follow_up=None, claim_text=None) is None
    long = "x" * 100
    tip = brief_failure_hint(follow_up=long, max_chars=20)
    assert tip is not None and tip.startswith("曾栽过：") and tip.endswith("…")
    assert len(tip) <= len("曾栽过：") + 20


def test_select_prefers_same_claim_then_neighbor_then_topic() -> None:
    focus = uuid4()
    neighbor = uuid4()
    other_topic = uuid4()
    unrelated = uuid4()
    cands = [
        _cand(claim_id=str(unrelated), topic="other", hours_ago=0),
        _cand(claim_id=str(other_topic), topic="transformers", hours_ago=1),
        _cand(claim_id=str(neighbor), topic="x", hours_ago=2),
        _cand(claim_id=str(focus), follow_up="same-claim tip", hours_ago=3),
    ]
    picked = select_failure_lessons(
        cands,
        claim_id=focus,
        neighbor_ids=[neighbor],
        topic="transformers",
    )
    assert [p.claim_id for p in picked] == [
        str(focus),
        str(neighbor),
        str(other_topic),
    ]
    assert str(unrelated) not in {p.claim_id for p in picked}


def test_select_dedupes_same_claim_verdict() -> None:
    focus = uuid4()
    cands = [
        _cand(claim_id=str(focus), verdict="owe_next", follow_up="first", hours_ago=0),
        _cand(claim_id=str(focus), verdict="owe_next", follow_up="dup", hours_ago=1),
        _cand(claim_id=str(focus), verdict="almost", follow_up="other-tier", hours_ago=2),
    ]
    picked = select_failure_lessons(cands, claim_id=focus)
    assert len(picked) == 2
    assert {(p.claim_id, p.verdict) for p in picked} == {
        (str(focus), "owe_next"),
        (str(focus), "almost"),
    }


def test_select_empty_neighbors_ok() -> None:
    focus = uuid4()
    picked = select_failure_lessons(
        [_cand(claim_id=str(focus), follow_up="solo")],
        claim_id=focus,
        neighbor_ids=[],
        topic=None,
    )
    assert len(picked) == 1
    assert picked[0].claim_id == str(focus)


def test_select_empty_when_no_match() -> None:
    focus = uuid4()
    picked = select_failure_lessons(
        [_cand(claim_id=str(uuid4()), topic="elsewhere")],
        claim_id=focus,
        topic="transformers",
    )
    assert picked == []
    assert (
        budget_failure_lesson_block(
            [_cand(claim_id=str(uuid4()), topic="elsewhere")],
            claim_id=focus,
            topic="transformers",
        )
        is None
    )


def test_select_respects_max_items() -> None:
    focus = uuid4()
    neighbors = [uuid4() for _ in range(5)]
    cands = [_cand(claim_id=str(focus), verdict="owe_next", follow_up="a")]
    for i, nid in enumerate(neighbors):
        cands.append(
            _cand(
                claim_id=str(nid),
                verdict="almost",
                follow_up=f"n{i}",
                hours_ago=i,
            )
        )
    picked = select_failure_lessons(
        cands,
        claim_id=focus,
        neighbor_ids=neighbors,
        max_items=FAILURE_LESSON_MAX_ITEMS,
    )
    assert len(picked) == FAILURE_LESSON_MAX_ITEMS
    assert picked[0].claim_id == str(focus)


def test_format_truncates_by_char_budget() -> None:
    focus = uuid4()
    long_tip = "x" * 200
    # Single oversize tip: budget too small for one line → None
    assert (
        format_failure_lesson_block(
            [_cand(claim_id=str(focus), follow_up=long_tip)],
            claim_id=focus,
            max_chars=30,
        )
        is None
    )
    one = format_failure_lesson_block(
        [_cand(claim_id=str(focus), follow_up=long_tip)],
        claim_id=focus,
        max_chars=220,
    )
    assert one is not None
    assert "你曾在这些点栽过" in one
    assert one.count("\n- ") == 1
    assert len(one) <= 220
    assert len(one) <= FAILURE_LESSON_MAX_CHARS

    # Multiple short tips: char cap drops later lines (宁缺毋滥)
    tips = [
        _cand(claim_id=str(focus), follow_up="tip-a-same", hours_ago=0),
        _cand(
            claim_id=str(uuid4()),
            follow_up="tip-b-neighbor",
            claim_text="neighbor claim",
            hours_ago=1,
        ),
        _cand(
            claim_id=str(uuid4()),
            follow_up="tip-c-neighbor",
            claim_text="other neighbor",
            hours_ago=2,
        ),
    ]
    neighbor_ids = [UUID(lesson.claim_id) for lesson in tips[1:]]
    capped = budget_failure_lesson_block(
        tips,
        claim_id=focus,
        neighbor_ids=neighbor_ids,
        max_chars=100,
    )
    assert capped is not None
    assert len(capped) <= 100
    assert capped.count("\n- ") >= 1
    assert capped.count("\n- ") < len(tips)
    assert "tip-a-same" in capped


def test_budget_respects_default_max_chars() -> None:
    focus = uuid4()
    neighbors = [uuid4() for _ in range(FAILURE_LESSON_MAX_ITEMS + 2)]
    cands = [
        _cand(
            claim_id=str(nid),
            follow_up=("tip-" + "z" * 180),
            claim_text=("claim-" + "y" * 80),
            hours_ago=i,
        )
        for i, nid in enumerate(neighbors)
    ]
    block = budget_failure_lesson_block(
        cands,
        claim_id=focus,
        neighbor_ids=neighbors,
    )
    assert block is not None
    assert len(block) <= FAILURE_LESSON_MAX_CHARS
    assert block.count("\n- ") <= FAILURE_LESSON_MAX_ITEMS


def test_build_prompt_omits_block_when_none() -> None:
    base = build_prompt(
        claim_text="C",
        history=[],
        answer=None,
        memory=[],
        failure_lesson_block=None,
    )
    assert "Prior miss lessons" not in base
    with_lessons = build_prompt(
        claim_text="C",
        history=[],
        answer=None,
        memory=[],
        failure_lesson_block=(
            "## Prior miss lessons\n你曾在这些点栽过：\n- [owe_next] tip"
        ),
    )
    assert "Prior miss lessons" in with_lessons
    assert "## Claim under examination\nC" in with_lessons


def test_topic_prompt_uses_compose_budget() -> None:
    """Topic examine must not bypass ContextBudget (trim lessons first)."""
    graph = "G" * 800
    lesson = "## Prior miss lessons\n你曾在这些点栽过：\n- [owe_next] " + ("L" * 200)
    raw_concat_len = len(graph) + len(lesson)
    assert raw_concat_len > DEFAULT_CONTEXT_BUDGET.total_max_chars

    prompt = build_topic_prompt(
        topic="transformers",
        claims=[],
        history=[],
        answer=None,
        memory=[],
        budget_block=graph,
        failure_lesson_block=lesson,
    )
    assert "## Topic\ntransformers" in prompt
    # Composed path: graph clipped to graph_max; lessons trimmed/dropped for total.
    # Full raw graph must not appear unclipped.
    assert "G" * 800 not in prompt
    assert prompt.count("G") <= DEFAULT_CONTEXT_BUDGET.graph_max_chars


def test_echo_prompt_injects_budgeted_block() -> None:
    block = (
        "## Prior miss lessons\n你曾在这些点栽过：\n- [almost] missed boundary"
    )
    prompt = build_echo_prompt(
        topic="pointers",
        history=[],
        answer=None,
        memory=[],
        failure_lesson_block=block,
    )
    assert "Prior miss lessons" in prompt
    assert "missed boundary" in prompt
    assert "Topic the learner is teaching back" in prompt


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as sess:
        yield sess
        await sess.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_build_failure_lesson_block_matches_claim(
    session: AsyncSession,
) -> None:
    claim_id = uuid4()
    other_id = uuid4()
    day_id = uuid4()
    session.add(
        LearningDayRow(id=day_id, user_id="local", day=date(2026, 7, 30), timezone="UTC")
    )
    session.add(
        ClaimRow(
            id=claim_id,
            user_id="local",
            text="Attention is all you need 的核心是什么",
            status=MasteryStatus.NOT_YET.value,
            topic="transformers",
        )
    )
    session.add(
        ClaimRow(
            id=other_id,
            user_id="local",
            text="Unrelated claim",
            status=MasteryStatus.NOT_YET.value,
            topic="other",
        )
    )
    session.add(
        PlanItemRow(
            id=uuid4(),
            day_id=day_id,
            title="考 attention",
            source=PlanItemSource.MANUAL.value,
            status="planned",
            claim_id=claim_id,
        )
    )
    await session.flush()

    assert (
        await memory_ops.build_failure_lesson_block(
            session, user_id="local", claim_id=claim_id, topic="transformers"
        )
        is None
    )

    await claim_ops.apply_examine_verdict(
        session, claim_id, verdict="owe_next", user_id="local"
    )
    pending = await memory_ops.list_pending_failure_digests(session, user_id="local")
    assert len(pending) == 1
    row = await session.get(MemoryEntryRow, pending[0].id)
    assert row is not None
    content = dict(row.content or {})
    content["follow_up"] = "没说清 Q/K/V 角色"
    row.content = content
    await session.flush()

    block = await memory_ops.build_failure_lesson_block(
        session, user_id="local", claim_id=claim_id, topic="transformers"
    )
    assert block is not None
    assert "你曾在这些点栽过" in block
    assert "owe_next" in block
    assert "Q/K/V" in block

    assert (
        await memory_ops.build_failure_lesson_block(
            session, user_id="local", claim_id=other_id, topic="other"
        )
        is None
    )


@pytest.mark.asyncio
async def test_e2e_owe_next_digest_reinjects_into_examine_prompt(
    session: AsyncSession,
) -> None:
    """Contract: owe_next → digest → re-examine prompt contains budgeted lessons."""
    claim_id = uuid4()
    day_id = uuid4()
    session.add(
        LearningDayRow(id=day_id, user_id="local", day=date(2026, 8, 3), timezone="UTC")
    )
    session.add(
        ClaimRow(
            id=claim_id,
            user_id="local",
            text="Explain self-attention Q/K/V",
            status=MasteryStatus.NOT_YET.value,
            topic="transformers",
        )
    )
    await session.flush()

    digest, block = await memory_ops.failure_writeback_and_lessons(
        session,
        user_id="local",
        claim_id=claim_id,
        claim_text="Explain self-attention Q/K/V",
        verdict="owe_next",
        topic="transformers",
        follow_up="没分清 Query 与 Key",
    )
    assert digest is not None
    assert block is not None
    assert len(block) <= FAILURE_LESSON_MAX_CHARS
    assert block.count("\n- ") <= FAILURE_LESSON_MAX_ITEMS

    prompt = build_prompt(
        claim_text="Explain self-attention Q/K/V",
        history=[],
        answer=None,
        memory=[],
        failure_lesson_block=block,
    )
    assert "Prior miss lessons" in prompt
    assert "没分清 Query 与 Key" in prompt

    # Dedup: second writeback same claim+verdict → no new digest; block still there.
    digest2, block2 = await memory_ops.failure_writeback_and_lessons(
        session,
        user_id="local",
        claim_id=claim_id,
        claim_text="Explain self-attention Q/K/V",
        verdict="owe_next",
        topic="transformers",
        follow_up="ignored dup tip",
    )
    assert digest2 is None
    assert block2 is not None
    assert "没分清 Query 与 Key" in block2

    # Claim-bound teach shares the same block source.
    echo_prompt = build_echo_prompt(
        topic="transformers",
        history=[],
        answer=None,
        memory=[],
        failure_lesson_block=block2,
    )
    assert "Prior miss lessons" in echo_prompt
