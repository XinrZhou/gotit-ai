"""Async loader for derived ``LearnerStateSnapshot`` (no new authoritative tables)."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gotit.core.learner_state import (
    ConfusionEdge,
    FailureLessonView,
    LearnerPrefsView,
    LearnerStateSnapshot,
    OwedSummary,
    WeakCluster,
    assemble_learner_state,
)
from gotit.core.models import MasteryStatus
from gotit.db.models import ClaimRow
from gotit.db.ops._common import DEFAULT_USER_ID
from gotit.db.ops.day import list_due_claims
from gotit.db.ops.graph import list_confused_edges
from gotit.db.ops.memory import list_memory


async def build_learner_state(
    session: AsyncSession,
    *,
    user_id: str = DEFAULT_USER_ID,
    as_of: date | None = None,
) -> LearnerStateSnapshot:
    """Read-only aggregate of owed / weak / confuse / lessons / light prefs."""
    day = as_of or date.today()
    due = await list_due_claims(session, day, user_id=user_id)
    reason_counts: dict[str, int] = defaultdict(int)
    sample_ids: list[UUID] = []
    for c in due:
        code = getattr(c, "due_reason_code", None) or "due"
        reason_counts[str(code)] += 1
        if len(sample_ids) < 12:
            sample_ids.append(c.id)
    owed = OwedSummary(
        due_count=len(due),
        due_reason_counts=dict(reason_counts),
        sample_claim_ids=sample_ids,
    )

    stmt = select(ClaimRow).where(
        ClaimRow.user_id == user_id,
        ClaimRow.status != MasteryStatus.MASTERED.value,
    )
    weak_rows = list((await session.execute(stmt)).scalars().all())
    by_topic: dict[str | None, list[UUID]] = defaultdict(list)
    for row in weak_rows:
        by_topic[row.topic].append(row.id)
    weak_clusters = [
        WeakCluster(
            topic=topic,
            claim_ids=ids[:20],
            severity=len(ids),
        )
        for topic, ids in sorted(
            by_topic.items(), key=lambda kv: (-len(kv[1]), str(kv[0] or ""))
        )[:12]
    ]

    edge_rows = await list_confused_edges(session, user_id=user_id, min_weight=1)
    confusions: list[ConfusionEdge] = []
    for e in edge_rows[:40]:
        a, b = e.source_claim_id, e.target_claim_id
        if str(a) > str(b):
            a, b = b, a
        confusions.append(ConfusionEdge(a=a, b=b, weight=int(e.weight)))

    digests = await list_memory(
        session, user_id=user_id, kind="failure_digest", limit=30
    )
    lessons: list[FailureLessonView] = []
    for entry in digests:
        raw_id = entry.content.get("claim_id") or entry.source.get("claim_id")
        cid: UUID | None
        try:
            cid = UUID(str(raw_id)) if raw_id else None
        except (TypeError, ValueError):
            cid = None
        follow = entry.content.get("follow_up") or entry.content.get("claim_text") or ""
        lessons.append(
            FailureLessonView(
                claim_id=cid,
                excerpt=str(follow)[:240],
                verdict=str(entry.content.get("verdict") or "") or None,
                topic=entry.topic,
                updated_at=entry.created_at.isoformat() if entry.created_at else None,
            )
        )

    prefs = await _load_prefs(session, user_id=user_id, as_of=day)
    return assemble_learner_state(
        as_of=day,
        user_id=user_id,
        owed_summary=owed,
        weak_clusters=weak_clusters,
        active_confusions=confusions,
        failure_lessons=lessons,
        interview_lane=prefs.interview_lane,
        prefs=prefs,
    )


async def _load_prefs(
    session: AsyncSession,
    *,
    user_id: str,
    as_of: date,
) -> LearnerPrefsView:
    prefs = LearnerPrefsView()
    try:
        from gotit.db.ops.bootcamp import get_bootcamp_status
        from gotit.db.ops.interview import interview_focus_for_today
        from gotit.db.ops.shell import get_digest_prefs

        boot = await get_bootcamp_status(session, user_id=user_id)
        prefs.bootcamp_lane = str(boot) if boot and boot != "none" else None

        digest = await get_digest_prefs(session, user_id=user_id)
        prefs.digest_enabled = bool(digest.news_enabled)

        now = datetime(as_of.year, as_of.month, as_of.day, tzinfo=UTC)
        focus = await interview_focus_for_today(session, now, user_id=user_id)
        if focus is not None:
            prefs.interview_lane = str(focus.ramp_tier)
    except Exception:  # noqa: BLE001 — prefs best-effort
        return prefs
    return prefs
