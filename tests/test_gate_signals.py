"""Pinned score/evidence gate signals (deterministic; no LLM)."""

from __future__ import annotations

from datetime import date

from gotit.core.loop import (
    MIN_EVIDENCE_CHARS,
    SCORE_PASS_FLOOR,
    deterministic_gate,
)


def test_stricter_of_two_unchanged_without_signals() -> None:
    g = deterministic_gate("passed", "passed")
    assert g.verdict == "passed"
    assert g.passed
    assert g.signals == []
    assert g.next_review_at is None


def test_low_score_blocks_pass() -> None:
    g = deterministic_gate(
        "passed",
        "passed",
        score=SCORE_PASS_FLOOR - 0.01,
        evidence="solid quote from claim text here",
    )
    assert g.verdict == "almost"
    assert not g.passed
    assert g.signals == ["low_score_blocks_pass"]
    assert "low_score_blocks_pass" in g.reason
    assert g.next_review_at == date.today()


def test_score_at_floor_allows_pass() -> None:
    g = deterministic_gate(
        "passed",
        "passed",
        score=SCORE_PASS_FLOOR,
        evidence="solid quote from claim text here",
    )
    assert g.verdict == "passed"
    assert g.signals == []


def test_empty_evidence_blocks_pass_when_provided() -> None:
    g = deterministic_gate(
        "passed",
        "passed",
        score=0.9,
        evidence="   ",
    )
    assert g.verdict == "almost"
    assert g.signals == ["empty_evidence_blocks_pass"]


def test_short_evidence_blocks_pass() -> None:
    g = deterministic_gate(
        "passed",
        "passed",
        score=0.9,
        evidence="x" * (MIN_EVIDENCE_CHARS - 1),
    )
    assert g.verdict == "almost"
    assert g.signals == ["empty_evidence_blocks_pass"]


def test_none_evidence_does_not_block_when_score_ok() -> None:
    """None = not provided (stub path); do not invent a downgrade."""
    g = deterministic_gate("passed", "passed", score=0.9, evidence=None)
    assert g.verdict == "passed"
    assert g.signals == []


def test_score_never_upgrades_stricter_base() -> None:
    g = deterministic_gate(
        "owe_next",
        "almost",
        score=0.99,
        evidence="long enough evidence string",
    )
    assert g.verdict == "owe_next"
    assert g.signals == []


def test_low_score_ignored_when_base_already_almost() -> None:
    g = deterministic_gate("almost", "almost", score=0.1, evidence="")
    assert g.verdict == "almost"
    assert g.signals == []
