"""Load budgeted companion state brief for chat orchestrator (read-only)."""

from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from gotit.core.companion_state_context import format_companion_state_brief
from gotit.db.ops._common import DEFAULT_USER_ID
from gotit.db.ops.ability_projection import build_ability_state
from gotit.db.ops.learner_state import build_learner_state
from gotit.db.ops.next_action import build_next_action


async def build_companion_state_brief(
    session: AsyncSession,
    *,
    user_id: str = DEFAULT_USER_ID,
    as_of: date | None = None,
) -> str:
    """Assemble Ability + next_action (+ light prefs) into chat context text.

    Never writes mastery. Intended for chat orchestrator injection only.
    """
    day = as_of or date.today()
    ability = await build_ability_state(session, user_id=user_id, as_of=day)
    next_act = await build_next_action(session, user_id=user_id, as_of=day)
    interview_lane: str | None = None
    bootcamp_lane: str | None = None
    try:
        snap = await build_learner_state(session, user_id=user_id, as_of=day)
        interview_lane = snap.interview_lane or snap.prefs.interview_lane
        bootcamp_lane = snap.prefs.bootcamp_lane
    except Exception:  # noqa: BLE001 — prefs best-effort
        pass
    return format_companion_state_brief(
        as_of=day,
        ability=ability,
        next_act=next_act,
        interview_lane=interview_lane,
        bootcamp_lane=bootcamp_lane,
    )
