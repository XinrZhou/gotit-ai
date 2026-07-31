"""First-pass bootcamp — empty show / skip / done / has-data quiet."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from gotit.core.models import MasteryStatus
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


@pytest.mark.asyncio
async def test_empty_library_shows_ingest(session: AsyncSession) -> None:
    day = date(2026, 7, 31)
    today = await day_ops.get_today(session, day, user_id="local")
    assert today.bootcamp is not None
    assert today.bootcamp.show is True
    assert today.bootcamp.step == "ingest"
    assert today.bootcamp.status == "none"
    assert today.bootcamp.claim_count == 0


@pytest.mark.asyncio
async def test_skip_hides_bootcamp(session: AsyncSession) -> None:
    await day_ops.put_bootcamp_status(session, "skipped", user_id="local")
    view = await day_ops.resolve_bootcamp(session, user_id="local")
    assert view.show is False
    assert view.status == "skipped"

    today = await day_ops.get_today(session, date(2026, 7, 31), user_id="local")
    assert today.bootcamp is not None
    assert today.bootcamp.show is False
    assert today.bootcamp.status == "skipped"


@pytest.mark.asyncio
async def test_done_hides_bootcamp(session: AsyncSession) -> None:
    await day_ops.put_bootcamp_status(session, "done", user_id="local")
    view = await day_ops.resolve_bootcamp(session, user_id="local")
    assert view.show is False
    assert view.status == "done"


@pytest.mark.asyncio
async def test_has_claims_no_nag(session: AsyncSession) -> None:
    session.add(
        ClaimRow(
            id=uuid4(),
            user_id="local",
            text="已有主张",
            status=MasteryStatus.QUEUED.value,
        )
    )
    await session.flush()
    view = await day_ops.resolve_bootcamp(session, user_id="local")
    assert view.show is False
    assert view.status == "none"
    assert view.claim_count == 1


@pytest.mark.asyncio
async def test_in_progress_verify_then_celebrate(session: AsyncSession) -> None:
    claim_id = uuid4()
    session.add(
        ClaimRow(
            id=claim_id,
            user_id="local",
            text="刚抽出的一句",
            status=MasteryStatus.NOT_YET.value,
        )
    )
    await session.flush()
    await day_ops.put_bootcamp_status(session, "in_progress", user_id="local")

    mid = await day_ops.resolve_bootcamp(session, user_id="local")
    assert mid.show is True
    assert mid.step == "verify"
    assert mid.claim_id == claim_id
    assert mid.claim_text == "刚抽出的一句"

    await day_ops.append_trajectory(
        session,
        user_id="local",
        claim_id=claim_id,
        topic=None,
        verdict="passed",
        gate_verdict="passed",
    )
    celeb = await day_ops.resolve_bootcamp(session, user_id="local")
    assert celeb.show is True
    assert celeb.step == "celebrate"
    assert celeb.gate_verdict == "passed"

    await day_ops.put_bootcamp_status(session, "done", user_id="local")
    done = await day_ops.resolve_bootcamp(session, user_id="local")
    assert done.show is False
    assert done.status == "done"
