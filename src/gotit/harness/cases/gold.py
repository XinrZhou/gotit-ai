"""Gold case set: small-sample quality compare (no LLM, no gate semantic change).

Covers: examine×critic → gate matrix samples, retest conversion (owe→passed),
and fixture presence for confuse-neighbour slugs.
"""

from __future__ import annotations

from datetime import date
from typing import cast
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from gotit.core.loop import deterministic_gate
from gotit.core.models import MasteryStatus
from gotit.db import ops as day_ops
from gotit.db.models import ClaimRow
from gotit.db.ops.memory import append_trajectory, list_trajectory
from gotit.harness import Case, CaseResult
from gotit.harness.gold_claims import (
    GOLD_CLAIMS,
    GOLD_CONFUSE_PAIR,
    by_slug,
    gate_pair_claims,
)


def _case_gate_pairs() -> Case:
    """Nail expected gate for each gold examine/critic pair (stricter-of-two)."""

    async def runner() -> CaseResult:
        rows: list[dict[str, object]] = []
        all_ok = True
        for claim in gate_pair_claims():
            assert claim.examine is not None and claim.critic is not None
            assert claim.expect_gate is not None
            gate = deterministic_gate(claim.examine, claim.critic)
            ok = gate.verdict == claim.expect_gate
            all_ok = all_ok and ok
            rows.append(
                {
                    "slug": claim.slug,
                    "examine": claim.examine,
                    "critic": claim.critic,
                    "gate": gate.verdict,
                    "expect": claim.expect_gate,
                    "ok": ok,
                }
            )
        return CaseResult(
            passed=all_ok,
            metrics={
                "rollup": "gate_consistent",
                "pairs": len(rows),
                "failed": sum(1 for r in rows if not r["ok"]),
            },
            trace=rows,
        )

    return Case(
        case_id="gold-gate-pairs",
        case_type="gate_matrix",
        layer="loop",
        runner=runner,
    )


def _case_retest_conversion(session: AsyncSession) -> Case:
    """owe_next then passed → trajectory two entries; claim ends mastered."""

    async def runner() -> CaseResult:
        meta = by_slug("gold-06-retest")
        claim_id = uuid4()
        user_id = "gold-local"
        session.add(
            ClaimRow(
                id=claim_id,
                user_id=user_id,
                text=meta.text,
                topic="gold",
                status=MasteryStatus.NOT_YET.value,
                source_excerpt="gold-set",
            )
        )
        await session.flush()

        # Round 1: hang
        await day_ops.apply_examine_verdict(
            session, claim_id, verdict="owe_next", user_id=user_id, as_of=date(2026, 7, 1)
        )
        await append_trajectory(
            session,
            user_id=user_id,
            claim_id=claim_id,
            topic="gold",
            verdict="owe_next",
            gate_verdict="owe_next",
            reason="gold round1",
        )

        # Round 2: pass
        wb = await day_ops.apply_examine_verdict(
            session, claim_id, verdict="passed", user_id=user_id, as_of=date(2026, 7, 15)
        )
        await append_trajectory(
            session,
            user_id=user_id,
            claim_id=claim_id,
            topic="gold",
            verdict="passed",
            gate_verdict="passed",
            reason="gold round2",
        )

        traj = await list_trajectory(session, user_id=user_id, claim_id=claim_id, limit=10)
        status = cast("dict[str, object]", wb["claim"])["status"]
        ok = (
            len(traj) >= 2
            and status == MasteryStatus.MASTERED.value
            and traj[0].content.get("gate_verdict") == "passed"
            and any(e.content.get("gate_verdict") == "owe_next" for e in traj)
        )
        return CaseResult(
            passed=ok,
            metrics={
                "slug": meta.slug,
                "trajectory_n": len(traj),
                "status": status,
            },
            trace=[
                {
                    "slug": meta.slug,
                    "examine": e.content.get("verdict"),
                    "gate": e.content.get("gate_verdict"),
                }
                for e in traj
            ],
        )

    return Case(
        case_id="gold-retest-conversion",
        case_type="retest",
        layer="system",
        runner=runner,
    )


def _case_fixture_inventory() -> Case:
    """Gold set stays 5–10 claims; confuse pair slugs resolve."""

    async def runner() -> CaseResult:
        n = len(GOLD_CLAIMS)
        a, b = GOLD_CONFUSE_PAIR
        ok = 5 <= n <= 10
        try:
            by_slug(a)
            by_slug(b)
            pair_ok = True
        except KeyError:
            pair_ok = False
        return CaseResult(
            passed=ok and pair_ok,
            metrics={"count": n, "confuse_pair": list(GOLD_CONFUSE_PAIR)},
            trace=[{"slug": c.slug, "role": c.role} for c in GOLD_CLAIMS],
        )

    return Case(
        case_id="gold-fixture-inventory",
        case_type="inventory",
        layer="system",
        runner=runner,
    )


def build_gold_cases(session: AsyncSession) -> list[Case]:
    return [
        _case_gate_pairs(),
        _case_retest_conversion(session),
        _case_fixture_inventory(),
    ]


def compare_rows_from_gate_pairs() -> list[dict[str, str]]:
    """Static rows for the before/after log table (no DB)."""
    rows: list[dict[str, str]] = []
    for claim in gate_pair_claims():
        assert claim.examine and claim.critic and claim.expect_gate
        gate = deterministic_gate(claim.examine, claim.critic)
        rows.append(
            {
                "claim": claim.slug,
                "examine": claim.examine,
                "critic": claim.critic,
                "gate": gate.verdict,
                "expect": claim.expect_gate,
                "diverge": "是" if claim.examine != claim.critic else "否",
                "note": claim.role,
            }
        )
    retest = by_slug("gold-06-retest")
    rows.append(
        {
            "claim": retest.slug,
            "examine": "owe_next→passed",
            "critic": "owe_next→passed",
            "gate": "owe_next→passed",
            "expect": "retest conversion",
            "diverge": "否",
            "note": retest.role,
        }
    )
    return rows
