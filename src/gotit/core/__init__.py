"""Domain types and verify-loop primitives (framework-free)."""

from gotit.core.loop import VerifyLoop
from gotit.core.models import CheckMode, CheckResult, Claim, LoopState, MasteryStatus

__all__ = [
    "Claim",
    "CheckMode",
    "CheckResult",
    "LoopState",
    "MasteryStatus",
    "VerifyLoop",
]
