"""Axiom structured-output recovery when the model returns prose."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai.exceptions import ModelAPIError

from gotit.core.agents.axiom import _recover_examine, _recover_topic, run_axiom
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


@pytest.mark.asyncio
async def test_run_axiom_recovers_model_api_error() -> None:
    agent = MagicMock()
    agent.run = AsyncMock(
        side_effect=ModelAPIError(model_name="test", message="Connection error.")
    )
    memory = MagicMock()
    memory.list_memory = AsyncMock(return_value=[])
    v = await run_axiom(agent, memory, claim_text="指针保存地址")
    assert v.done is False
    assert v.verdict is None
    assert "Connection error" in v.follow_up
