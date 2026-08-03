"""Deterministic verify-form routing (VISION P3 — form follows the claim).

LLM may suggest or narrate; preferred mode + resolve rules are code.
Mastery still closes via Critic + ``deterministic_gate`` (examine / teach).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from gotit.core.models import CheckMode

WorkflowName = Literal["examine", "teach", "drill"]
OpenKey = Literal["open_examine", "open_teach", "open_drill"]

_VALID = {m.value for m in CheckMode}

_TEACH_HINTS = (
    "回讲",
    "口述",
    "讲清楚",
    "用自己的话",
    "teach-back",
    "teach_back",
    "teachback",
    "explain aloud",
)


@dataclass(frozen=True)
class VerifyRoute:
    """UI / companion launch target for one claim."""

    mode: CheckMode
    workflow: WorkflowName
    action_id: str
    cta_label: str
    open_key: OpenKey


def parse_check_mode(raw: str | CheckMode | None) -> CheckMode | None:
    if raw is None:
        return None
    if isinstance(raw, CheckMode):
        return raw
    text = str(raw).strip().lower()
    if not text or text not in _VALID:
        return None
    return CheckMode(text)


def resolve_check_mode(
    preferred: str | CheckMode | None,
    *,
    project_id: UUID | None = None,
) -> CheckMode:
    """Pick an effective mode. Never invent drill without a project."""
    mode = parse_check_mode(preferred)
    if mode is None or mode == CheckMode.APPLY:
        return CheckMode.PROBE
    if mode == CheckMode.DRILL and project_id is None:
        return CheckMode.PROBE
    return mode


def route_verify_action(mode: CheckMode) -> VerifyRoute:
    if mode == CheckMode.TEACH_BACK:
        return VerifyRoute(
            mode=mode,
            workflow="teach",
            action_id="start_teach",
            cta_label="回讲",
            open_key="open_teach",
        )
    if mode == CheckMode.DRILL:
        return VerifyRoute(
            mode=mode,
            workflow="drill",
            action_id="start_drill",
            cta_label="练深挖",
            open_key="open_drill",
        )
    return VerifyRoute(
        mode=CheckMode.PROBE,
        workflow="examine",
        action_id="start_examine",
        cta_label="开考",
        open_key="open_examine",
    )


def route_for_claim(
    *,
    preferred: str | CheckMode | None,
    project_id: UUID | None = None,
) -> VerifyRoute:
    return route_verify_action(
        resolve_check_mode(preferred, project_id=project_id)
    )


def suggest_preferred_check_mode(
    *,
    text: str,
    tags: list[str] | None = None,
    project_id: UUID | None = None,
) -> CheckMode | None:
    """Light ingest heuristic. ``None`` → leave column null (probe default).

    Never suggests ``DRILL`` from ``project_id`` alone — drill is interview
    practice (prep-only), not a mastery-close form. Use ``start_drill`` /
    interview ramp for project deep-dive.
    """
    _ = project_id  # call-site compat; must not imply mastery form
    blob = f"{text or ''} {' '.join(tags or [])}".lower()
    if any(h in blob for h in _TEACH_HINTS):
        return CheckMode.TEACH_BACK
    return None
