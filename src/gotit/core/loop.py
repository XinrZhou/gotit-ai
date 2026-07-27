from __future__ import annotations

from gotit.core.models import Claim, LoopState


class VerifyLoop:
    """Skeleton state machine for the check → coach → recheck cycle.

    LLM / persistence adapters plug in later; this module stays framework-free.
    """

    def __init__(self) -> None:
        self.state: LoopState = LoopState.INGEST
        self.claims: list[Claim] = []

    def ingest_claims(self, claims: list[Claim]) -> None:
        if self.state not in {LoopState.INGEST, LoopState.DONE}:
            raise RuntimeError(f"cannot ingest in state {self.state}")
        self.claims = list(claims)
        self.state = LoopState.CLAIM if self.claims else LoopState.INGEST

    def begin_examine(self) -> None:
        if self.state not in {LoopState.CLAIM, LoopState.COACH, LoopState.QUEUE}:
            raise RuntimeError(f"cannot examine in state {self.state}")
        self.state = LoopState.EXAMINE

    def begin_coach(self) -> None:
        if self.state != LoopState.EXAMINE:
            raise RuntimeError(f"cannot coach in state {self.state}")
        self.state = LoopState.COACH

    def begin_gate(self) -> None:
        if self.state != LoopState.EXAMINE:
            raise RuntimeError(f"cannot gate in state {self.state}")
        self.state = LoopState.GATE

    def enqueue_missed(self) -> None:
        if self.state != LoopState.GATE:
            raise RuntimeError(f"cannot queue in state {self.state}")
        self.state = LoopState.QUEUE

    def mark_done(self) -> None:
        self.state = LoopState.DONE
