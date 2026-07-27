from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class CheckMode(StrEnum):
    PROBE = "probe"
    DRILL = "drill"
    APPLY = "apply"
    TEACH_BACK = "teach_back"


class MasteryStatus(StrEnum):
    NOT_YET = "not_yet"
    IN_PROGRESS = "in_progress"
    MASTERED = "mastered"
    QUEUED = "queued"


class LoopState(StrEnum):
    INGEST = "ingest"
    CLAIM = "claim"
    EXAMINE = "examine"
    COACH = "coach"
    GATE = "gate"
    QUEUE = "queue"
    DONE = "done"


class PlanItemSource(StrEnum):
    MANUAL = "manual"
    QUEUE = "queue"


class PlanItemStatus(StrEnum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    VERIFIED = "verified"
    FAILED = "failed"
    DEFERRED = "deferred"


class Claim(BaseModel):
    """A testable assertion extracted from study material."""

    id: UUID = Field(default_factory=uuid4)
    text: str
    source_excerpt: str | None = None
    status: MasteryStatus = MasteryStatus.NOT_YET
    source_note_id: UUID | None = None
    next_review_at: date | None = None


class CheckResult(BaseModel):
    claim_id: UUID
    mode: CheckMode
    passed: bool
    evidence: str
    score: float | None = None


class PlanItemView(BaseModel):
    id: UUID
    title: str
    source: PlanItemSource
    status: PlanItemStatus
    claim_id: UUID | None = None
    sort_order: int = 0
    due_at: date | None = None


class DayNoteView(BaseModel):
    id: UUID
    title: str | None = None
    body: str
    excerpt: str
    tags: list[str] = Field(default_factory=list)
    claim_ids: list[UUID] = Field(default_factory=list)
    created_at: datetime


class DayPlanView(BaseModel):
    date: date
    user_id: str
    items: list[PlanItemView] = Field(default_factory=list)


class ChatMessageView(BaseModel):
    id: UUID
    plan_item_id: UUID
    role: str
    text: str
    created_at: datetime


class TodayView(BaseModel):
    date: date
    plan: DayPlanView
    notes: list[DayNoteView] = Field(default_factory=list)
    due_claims: list[Claim] = Field(default_factory=list)
