"""Persist examine / teach / drill turns into companion thread messages."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from gotit.db import ops as day_ops
from gotit.db import session_scope

WORKFLOW_AGENTS = {
    "examine": "axiom",
    "teach": "echo",
    "drill": "sage",
}


def examine_agent_text(*, follow_up: str, done: bool, verdict: str | None) -> str:
    text = (follow_up or "").strip()
    if text:
        return text
    if done and verdict:
        return f"本轮判定：{verdict}"
    return ""


def teach_agent_text(
    *,
    done: bool,
    you_taught_well: bool | None,
    gaps: list[str],
    next_question: str | None,
) -> str:
    if done:
        label = "讲得清楚 ✓" if you_taught_well else "还有缺口"
        gap_s = f"\n缺口：{'；'.join(gaps)}" if gaps else ""
        return label + gap_s
    return (next_question or "继续讲讲？").strip()


def drill_agent_text(
    *,
    done: bool,
    depth_reached: int,
    gaps: list[str],
    follow_up: str | None,
) -> str:
    if done:
        gap_s = f"\n缺口：{'；'.join(gaps)}" if gaps else ""
        return f"这一轮练习结束（深度 {depth_reached}）{gap_s} · 不过门，不算掌握"
    return (follow_up or "说说你做了什么？").strip()


async def persist_workflow_exchange(
    *,
    thread_id: UUID | None,
    user_id: str,
    workflow: str,
    agent_text: str,
    user_text: str | None = None,
    extra_metadata: dict[str, Any] | None = None,
    title_seed: str | None = None,
) -> list[Any]:
    """No-op when ``thread_id`` is None. Raises ``KeyError`` on bad ownership."""
    if thread_id is None:
        return []
    agent_name = WORKFLOW_AGENTS[workflow]
    async with session_scope() as session:
        return await day_ops.append_workflow_exchange(
            session,
            thread_id=thread_id,
            user_id=user_id,
            workflow=workflow,
            agent_name=agent_name,
            agent_text=agent_text,
            user_text=user_text,
            extra_metadata=extra_metadata,
            title_seed=title_seed,
        )
