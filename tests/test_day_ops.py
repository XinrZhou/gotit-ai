from __future__ import annotations

from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from gotit.core.models import MasteryStatus, PlanItemSource, PlanItemStatus
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
async def test_manual_plan_and_notes(session: AsyncSession) -> None:
    day = date(2026, 7, 27)
    item = await day_ops.upsert_plan_item(session, day, title="Verify agent runtime")
    assert item.source == PlanItemSource.MANUAL
    assert item.status == PlanItemStatus.PLANNED

    note = await day_ops.add_note(session, day, "Agent runtime schedules tools.", title="Runtime")
    assert "schedules tools" in note.excerpt

    ingested = await day_ops.ingest_note(session, note.id)
    assert len(ingested["plan_items"]) >= 1
    claims = ingested["claims"]
    assert isinstance(claims, list) and len(claims) == 1

    plan = await day_ops.get_plan(session, day)
    assert len(plan.items) >= 2


@pytest.mark.asyncio
async def test_delete_plan_item(session: AsyncSession) -> None:
    day = date(2026, 7, 28)
    item = await day_ops.upsert_plan_item(session, day, title="Delete me")
    await day_ops.delete_plan_item(session, item.id)
    plan = await day_ops.get_plan(session, day)
    assert all(i.id != item.id for i in plan.items)
    with pytest.raises(KeyError):
        await day_ops.delete_plan_item(session, item.id)


@pytest.mark.asyncio
async def test_fill_queue_and_examine_writeback(session: AsyncSession) -> None:
    day = date(2026, 7, 27)
    claim = day_ops.stub_extract_claim("False fluency looks like knowing.")
    session.add(
        ClaimRow(
            id=claim.id,
            user_id="local",
            text=claim.text,
            source_excerpt=claim.source_excerpt,
            status=MasteryStatus.QUEUED.value,
            next_review_at=day,
        )
    )
    await session.flush()

    plan = await day_ops.fill_today_from_queue(session, day)
    assert any(i.claim_id == claim.id and i.source == PlanItemSource.QUEUE for i in plan.items)

    fail = await day_ops.write_mastery_outcome(
        session,
        claim.id,
        verdict="owe_next",
        source=day_ops.MASTERY_SOURCE_VERIFY,
        as_of=day,
    )
    assert fail["verdict"] == "owe_next"
    assert fail["claim"]["status"] == MasteryStatus.QUEUED.value
    assert fail["claim"]["next_review_at"] == (day + timedelta(days=1)).isoformat()

    ok = await day_ops.write_mastery_outcome(
        session,
        claim.id,
        verdict="passed",
        source=day_ops.MASTERY_SOURCE_VERIFY,
        as_of=day,
    )
    assert ok["claim"]["status"] == MasteryStatus.MASTERED.value


@pytest.mark.asyncio
async def test_apply_examine_verdict_continuous(session: AsyncSession) -> None:
    day = date(2026, 7, 27)
    claim = day_ops.stub_extract_claim("Continuous verdicts map to claim/plan states.")
    session.add(
        ClaimRow(
            id=claim.id,
            user_id="local",
            text=claim.text,
            source_excerpt=claim.source_excerpt,
            status=MasteryStatus.NOT_YET.value,
        )
    )
    await session.flush()

    almost = await day_ops.apply_examine_verdict(
        session, claim.id, verdict="almost", as_of=day
    )
    assert almost["verdict"] == "almost"
    assert almost["claim"]["status"] == MasteryStatus.IN_PROGRESS.value
    assert almost["claim"]["next_review_at"] == day.isoformat()

    passed = await day_ops.apply_examine_verdict(
        session, claim.id, verdict="passed", as_of=day
    )
    assert passed["claim"]["status"] == MasteryStatus.MASTERED.value
    assert passed["claim"]["next_review_at"] is None

    owe = await day_ops.apply_examine_verdict(
        session, claim.id, verdict="owe_next", as_of=day
    )
    assert owe["claim"]["status"] == MasteryStatus.QUEUED.value
    assert owe["claim"]["next_review_at"] == (day + timedelta(days=1)).isoformat()


@pytest.mark.asyncio
async def test_api_today_plan_notes(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    day = "2026-07-27"
    r = await client.post(
        f"/v1/days/{day}/plan/items",
        headers=auth_headers,
        json={"title": "Check context budget"},
    )
    assert r.status_code == 200
    assert r.json()["title"] == "Check context budget"

    r = await client.post(
        f"/v1/days/{day}/notes",
        headers=auth_headers,
        json={"body": "Inject the claim under test, not the whole notebook.", "title": "P4"},
    )
    assert r.status_code == 200
    note_id = r.json()["id"]

    r = await client.post(
        f"/v1/notes/{note_id}/ingest",
        headers=auth_headers,
        json={"add_plan_item": True},
    )
    assert r.status_code == 200
    claim_id = r.json()["claims"][0]["id"]

    r = await client.post(
        "/v1/examine",
        headers=auth_headers,
        json={"claim_id": claim_id, "verdict": "owe_next"},
    )
    assert r.status_code == 200
    assert r.json()["writeback"]["claim"]["status"] == "queued"

    r = await client.post(f"/v1/days/{day}/plan/fill-queue", headers=auth_headers)
    assert r.status_code == 200

    r = await client.get("/v1/today", headers=auth_headers, params={"day": day})
    assert r.status_code == 200
    body = r.json()
    assert body["date"] == day
    assert len(body["plan"]["items"]) >= 1
    assert len(body["notes"]) >= 1
