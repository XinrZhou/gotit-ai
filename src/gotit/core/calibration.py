"""Deterministic cold-start calibration (CAT-lite; framework-free; no LLM).

## Ability model (2PL, pinned by tests)

Difficulty ``b`` and ability ``θ`` share a 1–5 scale (prior ``θ₀ = 3``).
Discrimination ``a > 0`` (default ``1.0``).

    p(θ; a, b) = 1 / (1 + exp(-a · (θ − b)))
    I(θ)       = a² · p · (1 − p)          # Fisher information

After binary outcome ``y ∈ {0,1}``:

    θ ← θ + (y − p) · a / (1/se² + I)
    se² ← 1 / (1/se² + I)
    se  ← √se²

## Item selection

Among untested candidates, maximize a score of:

    info · rotate_penalty · neighbor_penalty

``rotate_penalty`` < 1 when ``knowledge_key`` matches the last answered key.
``neighbor_penalty`` < 1 when the claim is in ``downweight_ids`` (confused /
same-topic neighbors already inferred).

## Stop rules

| reason       | when                                              |
|--------------|---------------------------------------------------|
| converged    | ``se ≤ SE_STOP`` and ``n ≥ MIN_ITEMS``            |
| stable       | last ``STABLE_N`` Δθ all ``< STABLE_EPS`` and n≥MIN|
| max_items    | ``n ≥ MAX_ITEMS`` (default 10)                    |
| exhausted    | no candidates left                                |
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

DEFAULT_DIFFICULTY = 3
DEFAULT_DISCRIMINATION = 1.0
DEFAULT_KNOWLEDGE_KEY = "_untagged"

THETA0 = 3.0
SE0 = 1.5

MIN_ITEMS = 4
MAX_ITEMS = 10
SE_STOP = 0.45
STABLE_N = 3
STABLE_EPS = 0.15

ROTATE_PENALTY = 0.35
NEIGHBOR_PENALTY = 0.4

# Item-param writeback (verify / calibration outcomes → claim.calibration).
ITEM_B_STEP = 0.25
ITEM_A_STEP = 0.1
ITEM_SURPRISE_CENTER = 0.25  # surprise above this raises discrimination
ITEM_A_MIN = 0.05
ITEM_A_MAX = 3.0
ITEM_REF_THETA = THETA0  # fixed reference for surprise (no per-user θ needed)

StopReason = Literal["converged", "stable", "max_items", "exhausted"]
CalibOutcome = Literal["correct", "incorrect"]
GateVerdict = Literal["passed", "almost", "owe_next"]


@dataclass(frozen=True)
class CalibItem:
    """One calibration probe (usually backed by a Claim)."""

    id: UUID
    difficulty: int = DEFAULT_DIFFICULTY
    discrimination: float = DEFAULT_DISCRIMINATION
    knowledge_key: str = DEFAULT_KNOWLEDGE_KEY

    def __post_init__(self) -> None:
        d = max(1, min(5, int(self.difficulty)))
        a = max(0.05, float(self.discrimination))
        key = (self.knowledge_key or "").strip() or DEFAULT_KNOWLEDGE_KEY
        object.__setattr__(self, "difficulty", d)
        object.__setattr__(self, "discrimination", a)
        object.__setattr__(self, "knowledge_key", key)


@dataclass(frozen=True)
class AbilityState:
    theta: float = THETA0
    se: float = SE0


@dataclass(frozen=True)
class SelectResult:
    item: CalibItem
    info: float
    select_reason: str


@dataclass(frozen=True)
class StepUpdate:
    theta_before: float
    se_before: float
    theta_after: float
    se_after: float
    p: float
    info: float


def _parse_difficulty_float(raw: object) -> float:
    try:
        return max(1.0, min(5.0, float(raw)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float(DEFAULT_DIFFICULTY)


def normalize_calibration_meta(
    raw: dict[str, object] | None,
    *,
    topic: str | None = None,
) -> tuple[int, float, str]:
    """Fill defaults → (difficulty int 1–5, discrimination, knowledge_key).

    JSON may store continuous difficulty; CalibItem uses rounded int.
    """
    data = dict(raw or {})
    difficulty_raw = data.get("difficulty", DEFAULT_DIFFICULTY)
    discrimination_raw = data.get("discrimination", DEFAULT_DISCRIMINATION)
    key = data.get("knowledge_key")
    if not key:
        key = (topic or "").strip() or DEFAULT_KNOWLEDGE_KEY
    d_f = _parse_difficulty_float(difficulty_raw)
    d = max(1, min(5, int(round(d_f))))
    try:
        a = float(str(discrimination_raw))
    except (TypeError, ValueError):
        a = DEFAULT_DISCRIMINATION
    return (
        d,
        max(ITEM_A_MIN, a),
        str(key).strip() or DEFAULT_KNOWLEDGE_KEY,
    )


def gate_verdict_to_outcome(verdict: str) -> CalibOutcome:
    """Map mastery gate verdict to binary calibration outcome."""
    if verdict == "passed":
        return "correct"
    return "incorrect"


def update_item_calibration(
    raw: dict[str, object] | None,
    *,
    outcome: CalibOutcome,
    topic: str | None = None,
) -> dict[str, object]:
    """Update claim calibration JSON after one binary outcome (no LLM).

    - Fail → difficulty up (harder than labeled); pass → difficulty down.
    - Discrimination moves with surprise vs P(correct|θ=3, a, b).
    - Step sizes shrink with √(n+1). Counters n_attempts / n_passed / n_failed.
    """
    data = dict(raw or {})
    d_int, a, key = normalize_calibration_meta(data, topic=topic)
    d_f = _parse_difficulty_float(data.get("difficulty", d_int))
    try:
        n = max(0, int(data.get("n_attempts", 0) or 0))
    except (TypeError, ValueError):
        n = 0
    try:
        n_passed = max(0, int(data.get("n_passed", 0) or 0))
    except (TypeError, ValueError):
        n_passed = 0
    try:
        n_failed = max(0, int(data.get("n_failed", 0) or 0))
    except (TypeError, ValueError):
        n_failed = 0

    y = 1.0 if outcome == "correct" else 0.0
    shrink = math.sqrt(n + 1)
    step_b = ITEM_B_STEP / shrink
    d_after = max(1.0, min(5.0, d_f + (1.0 - 2.0 * y) * step_b))

    p0 = correct_probability(
        ITEM_REF_THETA, discrimination=a, difficulty=d_f
    )
    surprise = abs(y - p0)
    a_after = a + ITEM_A_STEP * (surprise - ITEM_SURPRISE_CENTER) / shrink
    a_after = max(ITEM_A_MIN, min(ITEM_A_MAX, a_after))

    n_after = n + 1
    if outcome == "correct":
        n_passed += 1
    else:
        n_failed += 1

    return {
        "difficulty": round(d_after, 4),
        "discrimination": round(a_after, 4),
        "knowledge_key": key,
        "n_attempts": n_after,
        "n_passed": n_passed,
        "n_failed": n_failed,
    }


def item_from_meta(
    claim_id: UUID,
    raw: dict[str, object] | None,
    *,
    topic: str | None = None,
) -> CalibItem:
    difficulty, discrimination, knowledge_key = normalize_calibration_meta(
        raw, topic=topic
    )
    return CalibItem(
        id=claim_id,
        difficulty=difficulty,
        discrimination=discrimination,
        knowledge_key=knowledge_key,
    )


def correct_probability(
    theta: float, *, discrimination: float, difficulty: float
) -> float:
    """2PL P(y=1 | θ)."""
    a = max(0.05, float(discrimination))
    z = a * (float(theta) - float(difficulty))
    if z >= 0:
        ez = math.exp(-z)
        return 1.0 / (1.0 + ez)
    ez = math.exp(z)
    return ez / (1.0 + ez)


def fisher_information(
    theta: float, *, discrimination: float, difficulty: float
) -> float:
    """I(θ) = a² · p · (1 − p)."""
    a = max(0.05, float(discrimination))
    p = correct_probability(theta, discrimination=a, difficulty=difficulty)
    return (a * a) * p * (1.0 - p)


def update_ability(
    state: AbilityState,
    *,
    outcome: CalibOutcome,
    discrimination: float,
    difficulty: float,
) -> StepUpdate:
    """Bayesian-ish θ / se update after one binary response."""
    theta = float(state.theta)
    se = max(float(state.se), 1e-6)
    a = max(0.05, float(discrimination))
    b = float(difficulty)
    p = correct_probability(theta, discrimination=a, difficulty=b)
    info = fisher_information(theta, discrimination=a, difficulty=b)
    y = 1.0 if outcome == "correct" else 0.0
    precision = 1.0 / (se * se)
    denom = precision + info
    if denom <= 0:
        denom = 1e-9
    theta_after = theta + (y - p) * a / denom
    theta_after = max(0.5, min(5.5, theta_after))
    se_after = math.sqrt(1.0 / denom)
    return StepUpdate(
        theta_before=theta,
        se_before=se,
        theta_after=theta_after,
        se_after=se_after,
        p=p,
        info=info,
    )


def select_next_item(
    candidates: list[CalibItem],
    *,
    theta: float,
    last_knowledge_key: str | None = None,
    downweight_ids: set[UUID] | frozenset[UUID] | None = None,
) -> SelectResult | None:
    """Pick the highest-scoring untested item (max info + rotate + neighbor)."""
    if not candidates:
        return None
    down = downweight_ids or frozenset()
    best: SelectResult | None = None
    best_score = float("-inf")
    for item in candidates:
        info = fisher_information(
            theta,
            discrimination=item.discrimination,
            difficulty=item.difficulty,
        )
        rotate = (
            ROTATE_PENALTY
            if last_knowledge_key and item.knowledge_key == last_knowledge_key
            else 1.0
        )
        neighbor = NEIGHBOR_PENALTY if item.id in down else 1.0
        score = info * rotate * neighbor
        tie = (item.discrimination, str(item.id))
        if best is None or score > best_score + 1e-12 or (
            abs(score - best_score) <= 1e-12
            and tie > (best.item.discrimination, str(best.item.id))
        ):
            reason_parts = ["max_info"]
            if rotate < 1.0:
                reason_parts.append("rotate")
            if neighbor < 1.0:
                reason_parts.append("neighbor_downweight")
            best = SelectResult(
                item=item,
                info=info,
                select_reason="+".join(reason_parts),
            )
            best_score = score
    return best


def should_stop(
    *,
    n_answered: int,
    se: float,
    recent_delta_theta: list[float],
    candidates_remaining: int,
    max_items: int = MAX_ITEMS,
    min_items: int = MIN_ITEMS,
    se_stop: float = SE_STOP,
) -> StopReason | None:
    """Return stop reason or None to continue."""
    if candidates_remaining <= 0:
        return "exhausted"
    if n_answered >= max_items:
        return "max_items"
    if n_answered >= min_items and se <= se_stop:
        return "converged"
    if n_answered >= min_items and len(recent_delta_theta) >= STABLE_N:
        window = recent_delta_theta[-STABLE_N:]
        if all(abs(d) < STABLE_EPS for d in window):
            return "stable"
    return None


def synthetic_outcome(
    *,
    true_theta: float,
    discrimination: float,
    difficulty: float,
    mode: Literal["bernoulli_threshold", "deterministic"] = "deterministic",
    rng_u: float | None = None,
) -> CalibOutcome:
    """Map a known ability to a binary answer (for synthetic replay).

    ``deterministic``: correct iff true_theta >= difficulty.
    ``bernoulli_threshold``: correct iff ``rng_u < p`` (caller supplies U~Uniform).
    """
    if mode == "deterministic":
        return "correct" if true_theta >= float(difficulty) else "incorrect"
    p = correct_probability(
        true_theta, discrimination=discrimination, difficulty=difficulty
    )
    u = 0.5 if rng_u is None else float(rng_u)
    return "correct" if u < p else "incorrect"
