"""State-driven next-action routing — pure function, no Workflow Engine.

Agent / companion / API should ask ``next_action(state)`` for the learner's
next step. Inputs are **derived** (owed due samples, ability rollup, interview
hint) — Claim mastery remains source of truth.

Reuses ``route_for_claim`` for form-follows-claim (examine / teach / drill launch
keys). Does **not** write mastery, invent a state-machine framework, or replace
schedule / gate.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from gotit.core.check_routing import OpenKey, WorkflowName, route_for_claim

NextActionKind = Literal["examine", "review", "teach", "drill", "calibrate"]

# Due reasons that mean "come back to this" rather than first-touch verify.
_REVIEW_DUE_REASONS = frozenset(
    {
        "almost_today",
        "owe_scheduled",
        "overdue",
        "confuse_boost",
        "depends",
        "queued",
    }
)

_REASON_TEXT: dict[str, str] = {
    "due_teach": "今日欠练，按 claim 偏好回讲",
    "due_drill": "今日欠练，按 claim 偏好深挖（练习场，不过门）",
    "due_review": "今日欠练，安排复习过门",
    "due_examine": "今日欠练，安排开考",
    "interview_drill": "面试临近，建议项目深挖（不过门）",
    "ability_review": "能力态仍有待复习弱点",
    "ability_examine": "能力态仍有未掌握 claim，建议开考",
    "calibrate": "冷启动：无欠练且有题可摸底",
    "pool_examine": "库中仍有未掌握 claim",
}


class NextActionClaimHint(BaseModel):
    """Minimal owed / weak claim facts for routing (caller-supplied)."""

    claim_id: UUID
    preferred_check_mode: str | None = None
    project_id: UUID | None = None
    due_reason_code: str | None = None
    topic: str | None = None
    text: str | None = None
    status: str | None = None


class NextActionState(BaseModel):
    """Compact derived state for ``next_action`` — not an authoritative table."""

    as_of: date
    user_id: str = ""
    due_claims: list[NextActionClaimHint] = Field(default_factory=list)
    weak_claims: list[NextActionClaimHint] = Field(default_factory=list)
    interview_drill_suggested: bool = False
    interview_project_id: UUID | None = None
    claim_count: int = 0
    mastered_count: int = 0
    pending_review_total: int = 0
    declining_ability: str | None = None
    calibration_eligible: bool = False


class NextAction(BaseModel):
    """One recommended next step (state-driven intent + launch hints)."""

    action: NextActionKind
    reason_code: str
    reason_text: str
    claim_id: UUID | None = None
    ability: str | None = None
    workflow: WorkflowName | Literal["calibrate"] | None = None
    open_key: OpenKey | None = None
    cta_label: str = ""
    preferred_check_mode: str | None = None


def _action_from_route(
    *,
    claim: NextActionClaimHint,
    source: Literal["due", "ability", "pool"],
    force_review: bool = False,
) -> NextAction:
    route = route_for_claim(
        preferred=claim.preferred_check_mode,
        project_id=claim.project_id,
    )
    if route.workflow == "teach":
        kind: NextActionKind = "teach"
        code = "due_teach" if source == "due" else "ability_examine"
    elif route.workflow == "drill":
        kind = "drill"
        code = "due_drill" if source == "due" else "ability_examine"
    elif force_review or (claim.due_reason_code or "") in _REVIEW_DUE_REASONS:
        kind = "review"
        code = "due_review" if source == "due" else "ability_review"
    else:
        kind = "examine"
        if source == "due":
            code = "due_examine"
        elif source == "pool":
            code = "pool_examine"
        else:
            code = "ability_examine"
    return NextAction(
        action=kind,
        reason_code=code,
        reason_text=_REASON_TEXT.get(code, code),
        claim_id=claim.claim_id,
        ability=claim.topic,
        workflow=route.workflow,
        open_key=route.open_key,
        cta_label=route.cta_label,
        preferred_check_mode=route.mode.value,
    )


def next_action(state: NextActionState) -> NextAction | None:
    """Decide the learner's next workflow step from derived state.

    Priority is deterministic code (see module design). Returns ``None`` when
    idle (e.g. nothing owed and empty library — UI may prompt 添加资料).
    """
    if state.due_claims:
        return _action_from_route(claim=state.due_claims[0], source="due")

    if state.interview_drill_suggested:
        return NextAction(
            action="drill",
            reason_code="interview_drill",
            reason_text=_REASON_TEXT["interview_drill"],
            claim_id=None,
            ability=None,
            workflow="drill",
            open_key="open_drill",
            cta_label="练深挖",
            preferred_check_mode="drill",
        )

    if state.pending_review_total > 0 and state.weak_claims:
        top = state.weak_claims[0]
        force_review = (top.status or "") in {"queued", "in_progress"}
        return _action_from_route(
            claim=top, source="ability", force_review=force_review
        )

    if state.calibration_eligible:
        return NextAction(
            action="calibrate",
            reason_code="calibrate",
            reason_text=_REASON_TEXT["calibrate"],
            workflow="calibrate",
            open_key=None,
            cta_label="摸底",
        )

    if state.claim_count > state.mastered_count and state.weak_claims:
        return _action_from_route(claim=state.weak_claims[0], source="pool")

    if state.claim_count > state.mastered_count:
        return NextAction(
            action="examine",
            reason_code="pool_examine",
            reason_text=_REASON_TEXT["pool_examine"],
            ability=state.declining_ability,
            workflow="examine",
            open_key="open_examine",
            cta_label="开考",
            preferred_check_mode="probe",
        )

    return None


def next_action_to_debug_dict(action: NextAction | None) -> dict[str, Any]:
    if action is None:
        return {"action": None, "reason_code": "idle"}
    return action.model_dump(mode="json")


__all__ = [
    "NextAction",
    "NextActionClaimHint",
    "NextActionKind",
    "NextActionState",
    "next_action",
    "next_action_to_debug_dict",
]
