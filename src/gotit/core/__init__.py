"""Domain types and verify-loop primitives (framework-free)."""

from gotit.core.learner_state import LearnerStateSnapshot, assemble_learner_state
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
    "LearnerStateSnapshot",
    "LoopState",
    "MasterySnapshot",
    "MasteryStatus",
    "PlanItemSource",
    "PlanItemStatus",
    "PlanItemView",
    "TodayView",
    "VerifyWorkflow",
    "assemble_learner_state",
    "deterministic_gate",
]
