from __future__ import annotations

from datetime import date
from uuid import UUID, uuid4

from gotit.core.models import (
    BallCustody,
    BallStage,
    GateResult,
)
from gotit.core.schedule import schedule_after_verdict

# Persistent ball-custody verify workflow: examine(axiom) → recheck(critic) →
# gate(deterministic code, no LLM). Pure transitions over `BallCustody` DTOs;
# orchestration persists via `db.ops.set_ball`.

_STRICTNESS = {"passed": 0, "almost": 1, "owe_next": 2}

# Explainable score/evidence floors — pinned by tests/test_gate_signals.py.
# ``None`` means "not provided" (stubs / gold matrix) → no downgrade.
SCORE_PASS_FLOOR = 0.4
MIN_EVIDENCE_CHARS = 8


def _apply_pass_signals(
    *,
    score: float | None,
    evidence: str | None,
) -> list[str]:
    """Signals that block a stricter-of-two ``passed`` (never upgrade)."""
    if score is not None and score < SCORE_PASS_FLOOR:
        return ["low_score_blocks_pass"]
    if evidence is not None and len(evidence.strip()) < MIN_EVIDENCE_CHARS:
        return ["empty_evidence_blocks_pass"]
    return []


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

    1. Stricter of examiner + critic (a single lenient agent cannot pass).
    2. If that base is ``passed``, optional score/evidence signals may
       downgrade to ``almost`` (never upgrade a stricter base).
    3. Map to ``schedule_after_verdict`` for ``next_review_at``.
    """
    ex = _STRICTNESS.get(examine_verdict, 1)
    rc = _STRICTNESS.get(recheck_verdict, 1)
    final_rank = max(ex, rc)
    final = next(v for v, r in _STRICTNESS.items() if r == final_rank)
    signals: list[str] = []
    if final == "passed":
        signals = _apply_pass_signals(score=score, evidence=evidence)
        if signals:
            final = "almost"

    today = as_of or date.today()
    sched = schedule_after_verdict(
        final, prior_failures=prior_failures, as_of=today
    )
    signal_suffix = f" [{', '.join(signals)}]" if signals else ""

    if final == "passed":
        return GateResult(
            passed=True,
            verdict="passed",
            next_review_at=sched.next_review_at,
            reason=(
                f"examine={examine_verdict} recheck={recheck_verdict} → 掌握"
                f"{signal_suffix}"
            ),
            signals=signals,
        )
    if final == "almost":
        return GateResult(
            passed=False,
            verdict="almost",
            next_review_at=sched.next_review_at,
            reason=(
                f"examine={examine_verdict} recheck={recheck_verdict} "
                f"→ 续考（今天接着）{signal_suffix}"
            ),
            signals=signals,
        )
    days = sched.interval_days if sched.interval_days is not None else 1
    return GateResult(
        passed=False,
        verdict="owe_next",
        next_review_at=sched.next_review_at,
        reason=(
            f"examine={examine_verdict} recheck={recheck_verdict} "
            f"→ 欠着，{days} 天后再考{signal_suffix}"
        ),
        signals=signals,
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
