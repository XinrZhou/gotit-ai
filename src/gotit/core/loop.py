from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

from gotit.core.models import (
    BallCustody,
    BallStage,
    Claim,
    GateResult,
    LoopState,
)
from gotit.core.schedule import schedule_after_verdict


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


# --- Persistent ball-custody verify workflow (companion-arch) ---
#
# The legacy `VerifyLoop` above is an in-memory skeleton kept for back-compat.
# The real verify-loop is a persistent ball-custody state machine: the ball
# moves examine(axiom) → recheck(critic) → gate(deterministic code, no LLM).
# State lives in the `ball_custody` table; the functions below are pure
# transitions over `BallCustody` DTOs — the orchestration layer persists.

_STRICTNESS = {"passed": 0, "almost": 1, "owe_next": 2}


def deterministic_gate(
    examine_verdict: str,
    recheck_verdict: str,
    *,
    score: float | None = None,
    evidence: str | None = None,
    prior_failures: int = 0,
    as_of: date | None = None,
) -> GateResult:
    """Deterministic mastery gate — no LLM.

    Takes the stricter of the examiner's and the critic's verdicts (so a single
    lenient agent cannot pass a claim), then maps to a GateResult with
    ``schedule_after_verdict`` for ``next_review_at`` (writeback may pass a
    richer ``prior_failures`` again).
    """
    del score, evidence  # reserved for future gate signals
    ex = _STRICTNESS.get(examine_verdict, 1)
    rc = _STRICTNESS.get(recheck_verdict, 1)
    final_rank = max(ex, rc)
    final = next(v for v, r in _STRICTNESS.items() if r == final_rank)
    today = as_of or date.today()
    sched = schedule_after_verdict(
        final, prior_failures=prior_failures, as_of=today
    )

    if final == "passed":
        return GateResult(
            passed=True,
            verdict="passed",
            next_review_at=sched.next_review_at,
            reason=f"examine={examine_verdict} recheck={recheck_verdict} → 掌握",
        )
    if final == "almost":
        return GateResult(
            passed=False,
            verdict="almost",
            next_review_at=sched.next_review_at,
            reason=f"examine={examine_verdict} recheck={recheck_verdict} → 续考（今天接着）",
        )
    days = sched.interval_days if sched.interval_days is not None else 1
    return GateResult(
        passed=False,
        verdict="owe_next",
        next_review_at=sched.next_review_at,
        reason=(
            f"examine={examine_verdict} recheck={recheck_verdict} "
            f"→ 欠着，{days} 天后再考"
        ),
    )


class VerifyWorkflow:
    """Pure transitions over `BallCustody` for the examine→recheck→gate loop.

    The orchestration layer (api/mcp) calls these to compute the next ball state,
    then persists via `db.ops.set_ball`. `gate()` is the terminal deterministic
    step; it does not call any agent.
    """

    @staticmethod
    def start(thread_id: UUID, claim_id: UUID) -> BallCustody:
        from datetime import UTC, datetime

        return BallCustody(
            id=uuid4(),
            thread_id=thread_id,
            holder="axiom",
            stage=BallStage.EXAMINE,
            context={"claim_id": str(claim_id)},
            acquired_at=datetime.now(UTC),
            expires_at=None,
        )

    @staticmethod
    def on_examine(
        ball: BallCustody,
        *,
        verdict: str,
        score: float | None,
        evidence: str | None,
    ) -> BallCustody:
        ctx = dict(ball.context)
        ctx["examine_verdict"] = verdict
        ctx["examine_score"] = score
        ctx["examine_evidence"] = evidence
        return BallCustody(
            id=ball.id,
            thread_id=ball.thread_id,
            holder="critic",
            stage=BallStage.RECHECK,
            context=ctx,
            acquired_at=ball.acquired_at,
            expires_at=None,
        )

    @staticmethod
    def on_recheck(ball: BallCustody, *, verdict: str) -> BallCustody:
        ctx = dict(ball.context)
        ctx["recheck_verdict"] = verdict
        return BallCustody(
            id=ball.id,
            thread_id=ball.thread_id,
            holder="gate",
            stage=BallStage.GATE,
            context=ctx,
            acquired_at=ball.acquired_at,
            expires_at=None,
        )

    @staticmethod
    def gate(ball: BallCustody, *, prior_failures: int = 0) -> GateResult:
        ctx = ball.context
        return deterministic_gate(
            examine_verdict=str(ctx.get("examine_verdict", "almost")),
            recheck_verdict=str(ctx.get("recheck_verdict", "almost")),
            score=ctx.get("examine_score"),
            evidence=ctx.get("examine_evidence"),
            prior_failures=prior_failures,
        )
