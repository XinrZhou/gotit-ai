"""Domain types and verify-loop primitives (framework-free)."""

from gotit.core.loop import VerifyWorkflow, deterministic_gate
from gotit.core.models import (
    CheckMode,
    CheckResult,
    Claim,
    DayNoteView,
    DayPlanView,
    LoopState,
    MasterySnapshot,
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
    "MasterySnapshot",
    "MasteryStatus",
    "PlanItemSource",
    "PlanItemStatus",
    "PlanItemView",
    "TodayView",
    "VerifyWorkflow",
    "deterministic_gate",
]
