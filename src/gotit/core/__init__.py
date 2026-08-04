"""Domain types and verify-loop primitives (framework-free)."""

from gotit.core.ability_projection import (
    AbilityStateProjection,
    assemble_ability_state,
)
from gotit.core.learner_state import LearnerStateSnapshot, assemble_learner_state
from gotit.core.loop import VerifyWorkflow, deterministic_gate
from gotit.core.next_action import NextAction, next_action
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
    "AbilityStateProjection",
    "Claim",
    "CheckMode",
    "CheckResult",
    "DayNoteView",
    "DayPlanView",
    "LearnerStateSnapshot",
    "LoopState",
    "MasterySnapshot",
    "MasteryStatus",
    "NextAction",
    "PlanItemSource",
    "PlanItemStatus",
    "PlanItemView",
    "TodayView",
    "VerifyWorkflow",
    "assemble_ability_state",
    "assemble_learner_state",
    "deterministic_gate",
    "next_action",
]
