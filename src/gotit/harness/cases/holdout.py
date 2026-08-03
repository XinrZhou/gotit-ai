"""Holdout case set — isolated from ``gold`` to catch overfitting.

Uses different fixtures/scenarios than gold claim slugs. Does **not** auto-tune
prompts or gate thresholds (VISION P5). Human adopt remains audit-only.
"""

from __future__ import annotations

from datetime import date
from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from gotit.api.verify_finalize import finalize_examine_with_gate
from gotit.core.loop import deterministic_gate
from gotit.core.models import MasteryStatus
from gotit.core.teach_verify import teach_examine_verdict
from gotit.harness import Case, CaseResult
from gotit.harness.cases._support import (
    claim_status,
    commit_after_gate,
    seed_claim,
    stub_settings,
    writeback_status,
)
from gotit.harness.gold_claims import GOLD_CLAIMS, by_slug

_AS_OF = date(2026, 8, 3)
_USER = "holdout-local"

# Gate pairs that are *not* copies of gold-01..05 matrix rows (extra combos).
_HOLDOUT_GATE_PAIRS: tuple[tuple[str, str, str], ...] = (
    ("passed", "almost", "almost"),
    ("almost", "owe_next", "owe_next"),
    ("owe_next", "passed", "owe_next"),
    ("owe_next", "almost", "owe_next"),
)


def _case_holdout_gate_matrix() -> Case:
    """Holdout gate matrix — pairs distinct from gold-01..05 documented rows."""

    async def runner() -> CaseResult:
        gold_pairs = {
            (c.examine, c.critic, c.expect_gate)
            for c in GOLD_CLAIMS
            if c.examine and c.critic and c.expect_gate
        }
        rows: list[dict[str, object]] = []
        all_ok = True
        overlap = 0
        for examine, critic, expect in _HOLDOUT_GATE_PAIRS:
            if (examine, critic, expect) in gold_pairs:
                overlap += 1
            gate = deterministic_gate(examine, critic)
            ok = gate.verdict == expect
            all_ok = all_ok and ok
            rows.append(
                {
                    "examine": examine,
                    "critic": critic,
                    "gate": gate.verdict,
                    "expect": expect,
                    "ok": ok,
                }
            )
        # Must not silently become a gold clone.
        distinct_ok = overlap == 0
        return CaseResult(
            passed=all_ok and distinct_ok,
            metrics={
                "rollup": "gate_consistent",
                "pairs": len(rows),
                "gold_overlap": overlap,
            },
            trace=rows,
        )

    return Case(
        case_id="holdout-gate-matrix",
        case_type="holdout_gate",
        layer="loop",
        runner=runner,
    )


def _case_holdout_score_evidence_finalize(session: AsyncSession) -> Case:
    """Holdout: score/evidence floors via finalize (stub Critic) — not gold slugs."""

    async def runner() -> CaseResult:
        settings = stub_settings()
        # low score
        low_id = await seed_claim(
            session, user_id=_USER, text="Holdout low-score claim (not gold)."
        )
        low = await finalize_examine_with_gate(
            session,
            claim_id=low_id,
            claim_text="Holdout low-score claim (not gold).",
            topic="holdout",
            examine_verdict="passed",
            examine_score=0.05,
            examine_evidence="long enough evidence for score case",
            user_id=_USER,
            settings=settings,
        )
        # empty evidence
        ev_id = await seed_claim(
            session, user_id=_USER, text="Holdout empty-evidence claim."
        )
        empty = await finalize_examine_with_gate(
            session,
            claim_id=ev_id,
            claim_text="Holdout empty-evidence claim.",
            topic="holdout",
            examine_verdict="passed",
            examine_score=0.99,
            examine_evidence="",
            user_id=_USER,
            settings=settings,
        )
        low_signals = cast("dict[str, Any]", low["gate"]).get("signals") or []
        empty_signals = cast("dict[str, Any]", empty["gate"]).get("signals") or []
        ok = (
            low["gate_verdict"] == "almost"
            and "low_score_blocks_pass" in low_signals
            and empty["gate_verdict"] == "almost"
            and "empty_evidence_blocks_pass" in empty_signals
            and await claim_status(session, low_id) != MasteryStatus.MASTERED.value
            and await claim_status(session, ev_id) != MasteryStatus.MASTERED.value
        )
        return CaseResult(
            passed=ok,
            metrics={
                "rollup": "gate_consistent",
                "low": low["gate_verdict"],
                "empty": empty["gate_verdict"],
            },
            trace=[
                {"low_id": str(low_id), "signals": list(low_signals)},
                {"ev_id": str(ev_id), "signals": list(empty_signals)},
            ],
        )

    return Case(
        case_id="holdout-score-evidence",
        case_type="holdout_finalize",
        layer="system",
        runner=runner,
    )


def _case_holdout_critic_stricter_write(session: AsyncSession) -> Case:
    """Holdout: examine almost + recheck owe_next → queued, never mastered."""

    async def runner() -> CaseResult:
        claim_id = await seed_claim(
            session, user_id=_USER, text="Holdout stricter recheck write."
        )
        gate, wb = await commit_after_gate(
            session,
            claim_id=claim_id,
            user_id=_USER,
            examine_verdict="almost",
            recheck_verdict="owe_next",
            as_of=_AS_OF,
        )
        status = writeback_status(wb)
        ok = (
            gate.verdict == "owe_next"
            and status == MasteryStatus.QUEUED.value
            and status != MasteryStatus.MASTERED.value
        )
        return CaseResult(
            passed=ok,
            metrics={
                "rollup": "no_spurious_write",
                "gate": gate.verdict,
                "status": status,
            },
            trace=[{"claim_id": str(claim_id)}],
        )

    return Case(
        case_id="holdout-stricter-recheck",
        case_type="holdout_write",
        layer="system",
        runner=runner,
    )


def _case_holdout_teach_mapping_finalize(session: AsyncSession) -> Case:
    """Holdout: teach_examine_verdict → finalize (separate from gold retest slug)."""

    async def runner() -> CaseResult:
        settings = stub_settings()
        pass_id = await seed_claim(
            session, user_id=_USER, text="Holdout teach-pass mapping."
        )
        fail_id = await seed_claim(
            session, user_id=_USER, text="Holdout teach-fail mapping."
        )
        p = await finalize_examine_with_gate(
            session,
            claim_id=pass_id,
            claim_text="Holdout teach-pass mapping.",
            topic="holdout",
            examine_verdict=teach_examine_verdict(True),
            examine_score=0.8,
            examine_evidence="teach-back evidence ok xx",
            user_id=_USER,
            settings=settings,
        )
        f = await finalize_examine_with_gate(
            session,
            claim_id=fail_id,
            claim_text="Holdout teach-fail mapping.",
            topic="holdout",
            examine_verdict=teach_examine_verdict(False),
            user_id=_USER,
            settings=settings,
        )
        # Ensure we did not accidentally use gold-06-retest text/slug contract.
        gold_retest = by_slug("gold-06-retest")
        ok = (
            p["gate_verdict"] == "passed"
            and f["gate_verdict"] == "owe_next"
            and await claim_status(session, pass_id) == MasteryStatus.MASTERED.value
            and await claim_status(session, fail_id) != MasteryStatus.MASTERED.value
            and gold_retest.text not in (
                "Holdout teach-pass mapping.",
                "Holdout teach-fail mapping.",
            )
        )
        return CaseResult(
            passed=ok,
            metrics={
                "rollup": "gate_consistent",
                "pass_gate": p["gate_verdict"],
                "fail_gate": f["gate_verdict"],
            },
            trace=[{"pass_id": str(pass_id), "fail_id": str(fail_id)}],
        )

    return Case(
        case_id="holdout-teach-mapping",
        case_type="holdout_teach",
        layer="system",
        runner=runner,
    )


def _case_holdout_not_gold_inventory() -> Case:
    """Static guard: holdout runner must not depend on gold slug inventory size."""

    async def runner() -> CaseResult:
        # Gold may grow; holdout only cares that its own pair table is non-empty
        # and disjoint from gold gate-pair triples (checked in matrix case).
        ok = len(_HOLDOUT_GATE_PAIRS) >= 3 and len(GOLD_CLAIMS) >= 1
        return CaseResult(
            passed=ok,
            metrics={
                "holdout_pairs": len(_HOLDOUT_GATE_PAIRS),
                "gold_claims": len(GOLD_CLAIMS),
            },
            trace=[{"holdout_pairs": list(_HOLDOUT_GATE_PAIRS)}],
        )

    return Case(
        case_id="holdout-isolation-guard",
        case_type="holdout_meta",
        layer="system",
        runner=runner,
    )


def build_holdout_cases(session: AsyncSession) -> list[Case]:
    return [
        _case_holdout_gate_matrix(),
        _case_holdout_score_evidence_finalize(session),
        _case_holdout_critic_stricter_write(session),
        _case_holdout_teach_mapping_finalize(session),
        _case_holdout_not_gold_inventory(),
    ]
