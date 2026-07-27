from __future__ import annotations

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


class Claim(BaseModel):
    """A testable assertion extracted from study material."""

    id: UUID = Field(default_factory=uuid4)
    text: str
    source_excerpt: str | None = None
    status: MasteryStatus = MasteryStatus.NOT_YET


class CheckResult(BaseModel):
    claim_id: UUID
    mode: CheckMode
    passed: bool
    evidence: str
    score: float | None = None
