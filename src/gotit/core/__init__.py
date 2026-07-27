"""Domain types and verify-loop primitives (framework-free)."""

from gotit.core.loop import VerifyLoop
from gotit.core.models import (
    CheckMode,
    CheckResult,
    Claim,
    DayNoteView,
    DayPlanView,
    LoopState,
    MasteryStatus,
    PlanItemSource,
    PlanItemStatus,
    PlanItemView,
    TodayView,
)

__all__ = [
    "Claim",
    "CheckMode",
    "CheckResult",
    "DayNoteView",
    "DayPlanView",
    "LoopState",
    "MasteryStatus",
    "PlanItemSource",
    "PlanItemStatus",
    "PlanItemView",
    "TodayView",
    "VerifyLoop",
]
