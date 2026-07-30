"""Shared constants and view helpers for db.ops subdomain modules."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from gotit.core.models import (
    Claim,
    DayNoteView,
    MasteryStatus,
    PlanItemSource,
    PlanItemStatus,
    PlanItemView,
)
from gotit.db.models import ClaimRow, DayNoteRow, PlanItemRow

DEFAULT_USER_ID = "local"
EXCERPT_LEN = 240


def _as_utc(dt: datetime | None) -> datetime:
    """SQLite often returns naive UTC; tag as UTC so JSON keeps +00:00 / Z."""
    if dt is None:
        return datetime.now(UTC)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _excerpt(body: str, limit: int = EXCERPT_LEN) -> str:
    text = body.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _plan_item_view(row: PlanItemRow, *, topic: str | None = None) -> PlanItemView:
    return PlanItemView(
        id=row.id,
        title=row.title,
        source=PlanItemSource(row.source),
        status=PlanItemStatus(row.status),
        claim_id=row.claim_id,
        sort_order=row.sort_order,
        due_at=row.due_at,
        due_time=getattr(row, "due_time", None),
        project_id=row.project_id,
        topic=topic,
    )


def _note_view(row: DayNoteRow, *, full_body: bool = False) -> DayNoteView:
    claim_ids = [UUID(str(c)) for c in (row.claim_ids or [])]
    body = row.body if full_body else ""
    day = row.learning_day.day if row.learning_day is not None else None
    return DayNoteView(
        id=row.id,
        title=row.title,
        body=body if full_body else _excerpt(row.body),
        excerpt=_excerpt(row.body),
        tags=list(row.tags or []),
        claim_ids=claim_ids,
        created_at=row.created_at or datetime.now(UTC),
        project_id=row.project_id,
        day=day,
    )


def _claim_view(row: ClaimRow) -> Claim:
    return Claim(
        id=row.id,
        text=row.text,
        source_excerpt=row.source_excerpt,
        status=MasteryStatus(row.status),
        source_note_id=row.source_note_id,
        next_review_at=row.next_review_at,
        topic=row.topic,
        tags=list(row.tags or []),
        project_id=row.project_id,
    )
