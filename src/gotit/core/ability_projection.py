"""Ability State Projection — derived per-topic read model.

**Source of truth** remains Claim mastery (``ClaimRow.status`` /
``next_review_at`` via ``write_mastery_outcome``) plus schedule / graph writers.
Trajectory and failure digests are **audit / cache**, not authority.

This module is a **read-only projection**: assemble Ability State Views from
already-loaded claims + trajectory (+ optional fail hints). It must never
write mastery, invent an Ability table, or act as a second state model.

Sibling projections:
- ``LearnerStateSnapshot`` — owed / weak clusters / lessons (ADR-0003)
- ``MasterySnapshot`` — today brief rollup
- **AbilityStateProjection** — per-topic ability lens for API / Chat / Workflow
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

AbilityTrend = Literal["improving", "stable", "declining", "unknown"]

_UNTAGGED = "(untagged)"
_PASS = frozenset({"passed", "pass", "true"})
_FAIL = frozenset({"almost", "owe_next"})
_PENDING_STATUS = frozenset({"queued", "in_progress"})


class AbilityClaimInput(BaseModel):
    """Minimal claim facts needed for projection (caller-supplied reads)."""

    id: UUID
    text: str = ""
    topic: str | None = None
    status: str
    next_review_at: date | None = None


class AbilityTrajectoryInput(BaseModel):
    """One audit trajectory line (newest-first lists preferred)."""

    claim_id: UUID | None = None
    topic: str | None = None
    gate_verdict: str | None = None
    reason: str | None = None


class AbilityWeakPoint(BaseModel):
    claim_id: UUID
    excerpt: str = ""
    status: str
    fail_hint: str | None = None


class AbilityStateView(BaseModel):
    """One ability (topic) rollup — derived, not authoritative."""

    ability: str
    claim_count: int = 0
    verified_count: int = 0
    mastered_count: int = 0
    weak_points: list[AbilityWeakPoint] = Field(default_factory=list)
    pending_review: int = 0
    recent_trend: AbilityTrend = "unknown"
    trajectory_passes: int = 0
    trajectory_failures: int = 0


class AbilityStateProjection(BaseModel):
    """Full user ability projection for agents / API / workflow."""

    as_of: date
    user_id: str
    abilities: list[AbilityStateView] = Field(default_factory=list)


def topic_key(topic: str | None) -> str:
    t = (topic or "").strip()
    return t if t else _UNTAGGED


def _gate_of(entry: AbilityTrajectoryInput) -> str:
    return str(entry.gate_verdict or "").strip().lower()


def compute_recent_trend(gate_verdicts: list[str], *, window: int = 5) -> AbilityTrend:
    """Map recent gate outcomes → coarse trend (code, not LLM)."""
    scored: list[int] = []
    for raw in gate_verdicts[:window]:
        g = str(raw or "").strip().lower()
        if g in _PASS:
            scored.append(1)
        elif g == "almost":
            scored.append(0)
        elif g == "owe_next":
            scored.append(-1)
    if not scored:
        return "unknown"
    mean = sum(scored) / len(scored)
    if mean > 0.2:
        return "improving"
    if mean < -0.2:
        return "declining"
    return "stable"


def assemble_ability_state(
    *,
    as_of: date,
    user_id: str,
    claims: list[AbilityClaimInput],
    trajectory: list[AbilityTrajectoryInput],
    fail_hints: dict[UUID, str] | None = None,
    weak_point_limit: int = 5,
) -> AbilityStateProjection:
    """Pure assembler — never writes mastery; callers supply authoritative reads."""
    hints = fail_hints or {}

    by_ability: dict[str, list[AbilityClaimInput]] = {}
    for c in claims:
        by_ability.setdefault(topic_key(c.topic), []).append(c)

    traj_by_ability: dict[str, list[AbilityTrajectoryInput]] = {}
    for e in trajectory:
        traj_by_ability.setdefault(topic_key(e.topic), []).append(e)

    # Claims that ever passed (audit) — may include topics with no current claim row.
    passed_claims: dict[str, set[UUID]] = {}
    for e in trajectory:
        if _gate_of(e) not in _PASS or e.claim_id is None:
            continue
        passed_claims.setdefault(topic_key(e.topic), set()).add(e.claim_id)

    abilities: list[AbilityStateView] = []
    all_keys = sorted(set(by_ability) | set(traj_by_ability), key=lambda k: k)
    for key in all_keys:
        rows = by_ability.get(key, [])
        traj = traj_by_ability.get(key, [])
        mastered = sum(1 for c in rows if c.status == "mastered")
        pending = 0
        candidates: list[AbilityClaimInput] = []
        for c in rows:
            if c.status == "mastered":
                continue
            due = c.next_review_at is not None and c.next_review_at <= as_of
            if due or c.status in _PENDING_STATUS:
                pending += 1
            candidates.append(c)
        # Prefer digest-backed / in-loop claims as weak points.
        candidates.sort(
            key=lambda c: (
                0 if c.id in hints else 1,
                0 if c.status in _PENDING_STATUS else 1,
                c.text or "",
            )
        )
        weak = [
            AbilityWeakPoint(
                claim_id=c.id,
                excerpt=(c.text or "")[:160],
                status=c.status,
                fail_hint=hints.get(c.id),
            )
            for c in candidates[:weak_point_limit]
        ]

        passes = sum(1 for e in traj if _gate_of(e) in _PASS)
        fails = sum(1 for e in traj if _gate_of(e) in _FAIL)
        gates = [_gate_of(e) for e in traj if _gate_of(e)]
        verified = len(passed_claims.get(key, set()) & {c.id for c in rows})
        # Also count audit-only passed claim ids when claim row missing from filter.
        if not rows:
            verified = len(passed_claims.get(key, set()))

        abilities.append(
            AbilityStateView(
                ability=key,
                claim_count=len(rows),
                verified_count=verified,
                mastered_count=mastered,
                weak_points=weak,
                pending_review=pending,
                recent_trend=compute_recent_trend(gates),
                trajectory_passes=passes,
                trajectory_failures=fails,
            )
        )

    # Prefer abilities with more pending / fails first (actionable), then name.
    abilities.sort(
        key=lambda a: (-a.pending_review, -a.trajectory_failures, a.ability),
    )
    return AbilityStateProjection(as_of=as_of, user_id=user_id, abilities=abilities)


def projection_to_debug_dict(projection: AbilityStateProjection) -> dict[str, Any]:
    """Compact dict for harness / companion traces."""
    return {
        "as_of": projection.as_of.isoformat(),
        "user_id": projection.user_id,
        "ability_count": len(projection.abilities),
        "abilities": [
            {
                "ability": a.ability,
                "claim_count": a.claim_count,
                "verified_count": a.verified_count,
                "mastered_count": a.mastered_count,
                "pending_review": a.pending_review,
                "recent_trend": a.recent_trend,
                "weak_points": len(a.weak_points),
            }
            for a in projection.abilities
        ],
    }


__all__ = [
    "AbilityClaimInput",
    "AbilityStateProjection",
    "AbilityStateView",
    "AbilityTrajectoryInput",
    "AbilityTrend",
    "AbilityWeakPoint",
    "assemble_ability_state",
    "compute_recent_trend",
    "projection_to_debug_dict",
    "topic_key",
]
