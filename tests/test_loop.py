from uuid import uuid4

from gotit.core.loop import VerifyWorkflow
from gotit.core.models import BallStage


def test_verify_workflow_ball_custody() -> None:
    thread_id = uuid4()
    claim_id = uuid4()
    ball = VerifyWorkflow.start(thread_id, claim_id)
    assert ball.holder == "axiom"
    assert ball.stage == BallStage.EXAMINE
    assert ball.context["claim_id"] == str(claim_id)

    ball = VerifyWorkflow.on_examine(
        ball, verdict="passed", score=0.9, evidence="solid answer here"
    )
    assert ball.holder == "critic"
    assert ball.stage == BallStage.RECHECK

    ball = VerifyWorkflow.on_recheck(ball, verdict="passed")
    assert ball.holder == "gate"
    assert ball.stage == BallStage.GATE

    gate = VerifyWorkflow.gate(ball, prior_failures=0)
    assert gate.verdict == "passed"
    assert gate.passed is True
