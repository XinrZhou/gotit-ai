"""Axiom structured-output recovery when the model returns prose."""

from gotit.core.agents.axiom import _recover_examine, _recover_topic
from gotit.core.models import Claim


def test_recover_examine_falls_back_to_question() -> None:
    v = _recover_examine(
        "The validation error indicates that the JSON provided is not valid.",
        claim_text="Transformer 用自注意力替代循环",
    )
    assert v.done is False
    assert v.verdict is None
    assert "Transformer" in v.follow_up or "自注意力" in v.follow_up


def test_recover_examine_parses_embedded_json() -> None:
    body = 'sure\n{"done": false, "verdict": null, "follow_up": "说说看？"}\n'
    v = _recover_examine(body, claim_text="x")
    assert v.done is False
    assert v.follow_up == "说说看？"


def test_recover_topic_falls_back() -> None:
    c = Claim(text="claim-a")
    v = _recover_topic("not json", claims=[c])
    assert v.current_claim_id == c.id
    assert v.done is False
    assert "claim-a" in v.follow_up
