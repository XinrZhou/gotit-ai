"""Form-follows-claim routing (deterministic; no LLM)."""

from __future__ import annotations

from uuid import uuid4

from gotit.core.check_routing import (
    resolve_check_mode,
    route_for_claim,
    route_verify_action,
    suggest_preferred_check_mode,
)
from gotit.core.models import CheckMode


def test_null_resolves_to_probe() -> None:
    assert resolve_check_mode(None) == CheckMode.PROBE
    assert route_for_claim(preferred=None).cta_label == "开考"


def test_teach_back_routes_to_teach() -> None:
    r = route_for_claim(preferred=CheckMode.TEACH_BACK)
    assert r.workflow == "teach"
    assert r.action_id == "start_teach"
    assert r.cta_label == "回讲"
    assert r.open_key == "open_teach"


def test_drill_without_project_degrades_to_probe() -> None:
    r = route_for_claim(preferred=CheckMode.DRILL, project_id=None)
    assert r.mode == CheckMode.PROBE
    assert r.action_id == "start_examine"


def test_drill_with_project() -> None:
    pid = uuid4()
    r = route_for_claim(preferred="drill", project_id=pid)
    assert r.mode == CheckMode.DRILL
    assert r.cta_label == "练深挖"
    assert r.open_key == "open_drill"


def test_apply_degrades_to_probe() -> None:
    assert resolve_check_mode(CheckMode.APPLY) == CheckMode.PROBE


def test_invalid_preferred_is_probe() -> None:
    assert resolve_check_mode("nonsense") == CheckMode.PROBE


def test_suggest_teach_from_text() -> None:
    assert (
        suggest_preferred_check_mode(text="用自己的话回讲 Transformer")
        == CheckMode.TEACH_BACK
    )


def test_suggest_project_does_not_imply_drill() -> None:
    """Project-linked claims still default to probe (gate path), not drill prep."""
    assert (
        suggest_preferred_check_mode(text="缓存击穿", project_id=uuid4()) is None
    )


def test_suggest_none_for_plain_claim() -> None:
    assert suggest_preferred_check_mode(text="Softmax 把分数变成概率") is None


def test_route_verify_action_probe() -> None:
    r = route_verify_action(CheckMode.PROBE)
    assert r.workflow == "examine"
