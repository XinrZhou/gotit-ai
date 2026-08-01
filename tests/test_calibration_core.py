"""Pin CAT-lite formulas: info, θ update, rotate, early stop."""

from __future__ import annotations

from uuid import uuid4

from gotit.core.calibration import (
    ITEM_B_STEP,
    MAX_ITEMS,
    MIN_ITEMS,
    AbilityState,
    CalibItem,
    correct_probability,
    fisher_information,
    gate_verdict_to_outcome,
    normalize_calibration_meta,
    select_next_item,
    should_stop,
    synthetic_outcome,
    update_ability,
    update_item_calibration,
)


def test_correct_probability_at_match() -> None:
    p = correct_probability(3.0, discrimination=1.0, difficulty=3.0)
    assert abs(p - 0.5) < 1e-9


def test_fisher_max_near_ability() -> None:
    # At θ=b, p=0.5 → I = a²/4
    i_mid = fisher_information(3.0, discrimination=2.0, difficulty=3.0)
    i_far = fisher_information(3.0, discrimination=2.0, difficulty=5.0)
    assert abs(i_mid - 1.0) < 1e-9  # 4 * 0.25 = 1
    assert i_mid > i_far


def test_update_correct_raises_theta() -> None:
    before = AbilityState(theta=3.0, se=1.5)
    step = update_ability(
        before, outcome="correct", discrimination=1.5, difficulty=3.0
    )
    assert step.theta_after > step.theta_before
    assert step.se_after < step.se_before


def test_update_incorrect_lowers_theta() -> None:
    before = AbilityState(theta=3.0, se=1.5)
    step = update_ability(
        before, outcome="incorrect", discrimination=1.5, difficulty=3.0
    )
    assert step.theta_after < step.theta_before


def test_select_prefers_high_discrimination_near_theta() -> None:
    near_hi = CalibItem(id=uuid4(), difficulty=3, discrimination=2.5, knowledge_key="a")
    near_lo = CalibItem(id=uuid4(), difficulty=3, discrimination=0.5, knowledge_key="b")
    far = CalibItem(id=uuid4(), difficulty=5, discrimination=2.5, knowledge_key="c")
    picked = select_next_item([near_lo, far, near_hi], theta=3.0)
    assert picked is not None
    assert picked.item.id == near_hi.id


def test_select_rotates_knowledge_key() -> None:
    same = CalibItem(id=uuid4(), difficulty=3, discrimination=2.0, knowledge_key="redis")
    other = CalibItem(id=uuid4(), difficulty=3, discrimination=1.9, knowledge_key="sql")
    # Without rotate, same (higher a) wins; with last=redis, other should win.
    picked = select_next_item(
        [same, other], theta=3.0, last_knowledge_key="redis"
    )
    assert picked is not None
    assert picked.item.id == other.id
    unpenalized = select_next_item([same, other], theta=3.0)
    assert unpenalized is not None
    assert unpenalized.item.id == same.id


def test_select_downweights_neighbors() -> None:
    neighbor = CalibItem(id=uuid4(), difficulty=3, discrimination=2.0, knowledge_key="a")
    other = CalibItem(id=uuid4(), difficulty=3, discrimination=1.9, knowledge_key="b")
    picked = select_next_item(
        [neighbor, other],
        theta=3.0,
        downweight_ids={neighbor.id},
    )
    assert picked is not None
    assert picked.item.id == other.id


def test_adaptive_difficulty_after_streak() -> None:
    """After several corrects, next pick prefers harder items."""
    easy = CalibItem(id=uuid4(), difficulty=2, discrimination=1.5, knowledge_key="k1")
    hard = CalibItem(id=uuid4(), difficulty=5, discrimination=1.5, knowledge_key="k2")
    state = AbilityState()
    for _ in range(4):
        step = update_ability(
            state, outcome="correct", discrimination=1.5, difficulty=3.0
        )
        state = AbilityState(theta=step.theta_after, se=step.se_after)
    picked = select_next_item([easy, hard], theta=state.theta)
    assert picked is not None
    assert picked.item.id == hard.id


def test_should_stop_max_and_exhausted() -> None:
    assert (
        should_stop(
            n_answered=MAX_ITEMS,
            se=1.0,
            recent_delta_theta=[],
            candidates_remaining=5,
        )
        == "max_items"
    )
    assert (
        should_stop(
            n_answered=2,
            se=1.0,
            recent_delta_theta=[],
            candidates_remaining=0,
        )
        == "exhausted"
    )


def test_should_stop_converged() -> None:
    assert (
        should_stop(
            n_answered=MIN_ITEMS,
            se=0.3,
            recent_delta_theta=[0.5, 0.4],
            candidates_remaining=3,
        )
        == "converged"
    )


def test_should_stop_stable() -> None:
    assert (
        should_stop(
            n_answered=MIN_ITEMS,
            se=0.9,
            recent_delta_theta=[0.05, -0.04, 0.02],
            candidates_remaining=3,
        )
        == "stable"
    )


def test_should_continue_before_min() -> None:
    assert (
        should_stop(
            n_answered=2,
            se=0.2,
            recent_delta_theta=[0.01, 0.01],
            candidates_remaining=5,
        )
        is None
    )


def test_synthetic_deterministic() -> None:
    assert (
        synthetic_outcome(
            true_theta=4.0, discrimination=1.0, difficulty=3.0, mode="deterministic"
        )
        == "correct"
    )
    assert (
        synthetic_outcome(
            true_theta=2.0, discrimination=1.0, difficulty=3.0, mode="deterministic"
        )
        == "incorrect"
    )


def test_gate_verdict_to_outcome() -> None:
    assert gate_verdict_to_outcome("passed") == "correct"
    assert gate_verdict_to_outcome("almost") == "incorrect"
    assert gate_verdict_to_outcome("owe_next") == "incorrect"


def test_normalize_accepts_float_difficulty() -> None:
    d, a, key = normalize_calibration_meta(
        {"difficulty": 3.6, "discrimination": 1.2, "knowledge_key": "redis"}
    )
    assert d == 4
    assert abs(a - 1.2) < 1e-9
    assert key == "redis"


def test_item_fail_raises_difficulty() -> None:
    before = {"difficulty": 3.0, "discrimination": 1.0, "knowledge_key": "x"}
    after = update_item_calibration(before, outcome="incorrect")
    assert float(after["difficulty"]) > 3.0
    assert abs(float(after["difficulty"]) - (3.0 + ITEM_B_STEP)) < 1e-9
    assert after["n_attempts"] == 1
    assert after["n_failed"] == 1
    assert after["n_passed"] == 0


def test_item_pass_lowers_difficulty() -> None:
    before = {"difficulty": 3.0, "discrimination": 1.0, "knowledge_key": "x"}
    after = update_item_calibration(before, outcome="correct")
    assert float(after["difficulty"]) < 3.0
    assert after["n_passed"] == 1


def test_item_step_shrinks_with_attempts() -> None:
    state: dict[str, object] = {
        "difficulty": 3.0,
        "discrimination": 1.0,
        "knowledge_key": "x",
    }
    first = update_item_calibration(state, outcome="incorrect")
    second = update_item_calibration(first, outcome="incorrect")
    delta1 = float(first["difficulty"]) - 3.0
    delta2 = float(second["difficulty"]) - float(first["difficulty"])
    assert delta2 < delta1
    assert second["n_attempts"] == 2


def test_item_difficulty_clipped() -> None:
    hard = update_item_calibration(
        {"difficulty": 5.0, "discrimination": 1.0},
        outcome="incorrect",
    )
    assert float(hard["difficulty"]) == 5.0
    easy = update_item_calibration(
        {"difficulty": 1.0, "discrimination": 1.0},
        outcome="correct",
    )
    assert float(easy["difficulty"]) == 1.0
