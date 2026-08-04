"""Unit tests for Verify Run envelope types (no I/O)."""

from __future__ import annotations

from uuid import uuid4

from gotit.core.agent_run import (
    evaluate_write_intent,
    intent_may_commit,
    make_idempotency_key,
    new_agent_run,
    propose_write_intent,
    reject_write_intent,
)


def test_propose_evaluate_accepts_and_may_commit() -> None:
    run = new_agent_run(user_id="u", claim_id=uuid4())
    intent = propose_write_intent(
        run,
        claim_id=run.claim_id or uuid4(),
        examine_verdict="passed",
        recheck_verdict="passed",
        examine_score=0.9,
        examine_evidence="enough evidence characters",
    )
    assert intent.status == "proposed"
    assert not intent_may_commit(intent)
    accepted = evaluate_write_intent(intent)
    assert accepted.status == "accepted"
    assert accepted.gate is not None
    assert accepted.gate.verdict == "passed"
    assert intent_may_commit(accepted)


def test_rejected_intent_cannot_commit() -> None:
    run = new_agent_run(user_id="u", claim_id=uuid4())
    intent = propose_write_intent(
        run,
        claim_id=run.claim_id or uuid4(),
        examine_verdict="passed",
        recheck_verdict="passed",
        examine_evidence="enough evidence characters",
    )
    accepted = evaluate_write_intent(intent)
    rejected = reject_write_intent(accepted, reason="abort")
    assert rejected.status == "rejected"
    assert not intent_may_commit(rejected)


def test_gate_downgrades_proposal_before_commit_authority() -> None:
    """LLM may propose passed; gate verdict is what commit would use."""
    run = new_agent_run(user_id="u", claim_id=uuid4())
    intent = propose_write_intent(
        run,
        claim_id=run.claim_id or uuid4(),
        examine_verdict="passed",
        recheck_verdict="owe_next",
        examine_score=0.99,
        examine_evidence="enough evidence characters",
    )
    accepted = evaluate_write_intent(intent)
    assert accepted.gate is not None
    assert accepted.gate.verdict == "owe_next"
    assert accepted.examine_verdict == "passed"  # proposal preserved


def test_idempotency_key_stable() -> None:
    run_id = uuid4()
    claim_id = uuid4()
    a = make_idempotency_key(
        run_id=run_id, claim_id=claim_id, gate_verdict="passed", gate_reason="x"
    )
    b = make_idempotency_key(
        run_id=run_id, claim_id=claim_id, gate_verdict="passed", gate_reason="x"
    )
    assert a == b
    assert len(a) == 24
