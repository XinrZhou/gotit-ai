"""Companion builtin tools — whitelist for chat agent tool-calling.

Thin wrappers over ``db.ops`` (same surface REST/MCP use). Lives in ``api/`` so
``gotit.core`` stays free of session / FastAPI / MCP imports. Tool call digests
are recorded for message ``metadata.tool_calls`` (explainable / replayable).

``start_examine`` prepares an open-examine payload and may soft-mark a claim
in_progress / on today's plan — it does **not** run Critic or the mastery gate.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from gotit.core.models import MasteryStatus, PlanItemSource, PlanItemStatus
from gotit.db import ops as day_ops
from gotit.db.models import ClaimRow, DayNoteRow, LearningDayRow

_MEMORY_NOTE_MAX = 400
_SUMMARY_MAX = 240
_ARGS_DIGEST_MAX = 160
_DUE_LIST_CAP = 12


@dataclass
class ToolCallRecord:
    name: str
    args_digest: str
    ok: bool
    summary: str
    open_examine: dict[str, object] | None = None

    def as_dict(self) -> dict[str, object]:
        out: dict[str, object] = {
            "name": self.name,
            "args_digest": self.args_digest,
            "ok": self.ok,
            "summary": self.summary,
        }
        if self.open_examine is not None:
            out["open_examine"] = self.open_examine
        return out


@dataclass
class ToolCallRecorder:
    """Side-channel trail of builtin tool invocations for message metadata."""

    calls: list[ToolCallRecord] = field(default_factory=list)

    def record(
        self,
        name: str,
        *,
        args: dict[str, Any],
        ok: bool,
        summary: str,
        open_examine: dict[str, object] | None = None,
    ) -> None:
        self.calls.append(
            ToolCallRecord(
                name=name,
                args_digest=_args_digest(args),
                ok=ok,
                summary=_clip(summary, _SUMMARY_MAX),
                open_examine=open_examine,
            )
        )

    def as_metadata(self) -> list[dict[str, object]]:
        return [c.as_dict() for c in self.calls]

    def last_open_examine(self) -> dict[str, object] | None:
        """Most recent successful open-examine payload in this recorder."""
        for call in reversed(self.calls):
            if call.ok and call.open_examine is not None:
                return call.open_examine
        return None


def _clip(text: str, limit: int) -> str:
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    return t[: max(0, limit - 1)] + "…"


def _args_digest(args: dict[str, Any]) -> str:
    compact = {k: v for k, v in args.items() if v is not None and v != ""}
    raw = json.dumps(compact, ensure_ascii=False, default=str, sort_keys=True)
    return _clip(raw, _ARGS_DIGEST_MAX)


def _claim_brief(claim: Any) -> dict[str, object]:
    status = claim.status.value if hasattr(claim.status, "value") else str(claim.status)
    return {
        "id": str(claim.id),
        "text": _clip(claim.text, 120),
        "status": status,
        "topic": claim.topic,
        "next_review_at": (claim.next_review_at.isoformat() if claim.next_review_at else None),
    }


def build_companion_tools(
    session: AsyncSession,
    *,
    user_id: str,
    day: date,
    thread_id: UUID | None = None,
    recorder: ToolCallRecorder | None = None,
) -> list[Any]:
    """Return pydantic-ai ``Tool`` instances for the companion whitelist."""
    from pydantic_ai import Tool

    rec = recorder or ToolCallRecorder()

    async def get_today() -> dict[str, object]:
        """Read today's plan items and due claims (real DB state)."""
        args: dict[str, Any] = {"day": day.isoformat()}
        try:
            view = await day_ops.get_today(session, day, user_id=user_id)
            plan_items = [
                {
                    "title": it.title,
                    "status": (it.status.value if hasattr(it.status, "value") else str(it.status)),
                    "due_time": it.due_time,
                    "claim_id": str(it.claim_id) if it.claim_id else None,
                }
                for it in view.plan.items[:8]
            ]
            due = [_claim_brief(c) for c in view.due_claims[:_DUE_LIST_CAP]]
            out: dict[str, object] = {
                "date": view.date.isoformat(),
                "plan_count": len(view.plan.items),
                "plan_items": plan_items,
                "due_count": len(view.due_claims),
                "due_claims": due,
                "notes_count": len(view.notes),
            }
            rec.record(
                "get_today",
                args=args,
                ok=True,
                summary=(
                    f"{view.date.isoformat()}：计划 {len(view.plan.items)} 条，"
                    f"欠账 {len(view.due_claims)} 条"
                ),
            )
            return out
        except Exception as exc:  # noqa: BLE001 — surface to model + metadata
            rec.record(
                "get_today",
                args=args,
                ok=False,
                summary=f"{type(exc).__name__}: {exc}",
            )
            return {"ok": False, "error": str(exc)}

    async def list_due_claims() -> dict[str, object]:
        """List claims due for review today (queued / not_yet / in_progress)."""
        args: dict[str, Any] = {"day": day.isoformat()}
        try:
            rows = await day_ops.list_due_claims(session, day, user_id=user_id)
            claims = [
                _claim_brief(day_ops._claim_view(r))  # noqa: SLF001
                for r in rows[:_DUE_LIST_CAP]
            ]
            out: dict[str, object] = {
                "date": day.isoformat(),
                "count": len(rows),
                "claims": claims,
            }
            rec.record(
                "list_due_claims",
                args=args,
                ok=True,
                summary=f"欠账 {len(rows)} 条",
            )
            return out
        except Exception as exc:  # noqa: BLE001
            rec.record(
                "list_due_claims",
                args=args,
                ok=False,
                summary=f"{type(exc).__name__}: {exc}",
            )
            return {"ok": False, "error": str(exc)}

    async def start_examine(
        claim_id: str | None = None,
        note_id: str | None = None,
    ) -> dict[str, object]:
        """Prepare an examine launch payload (claim or note). Does not run the gate.

        If neither id is given, picks the first due claim. May place the claim on
        today's plan and soft-mark in_progress — mastery still requires Critic+gate
        via /v1/examine.
        """
        args: dict[str, Any] = {
            "claim_id": claim_id,
            "note_id": note_id,
            "thread_id": str(thread_id) if thread_id else None,
        }
        try:
            if note_id:
                nid = UUID(note_id)
                note = await session.get(DayNoteRow, nid)
                if note is None:
                    raise KeyError(f"note not found: {note_id}")
                day_row = await session.get(LearningDayRow, note.day_id)
                if day_row is None or day_row.user_id != user_id:
                    raise KeyError(f"note not found: {note_id}")
                claim_ids = [str(c) for c in (note.claim_ids or [])]
                if not claim_ids:
                    raise ValueError("note has no claims yet — ingest or curate first")
                open_payload: dict[str, object] = {
                    "action": "open_examine",
                    "note_id": str(nid),
                    "note_title": note.title,
                    "claim_ids": claim_ids,
                    "thread_id": str(thread_id) if thread_id else None,
                }
                out: dict[str, object] = {
                    **open_payload,
                    "ok": True,
                    "hint": "可在气泡下点「开考」，或用 note_id 调用 /v1/examine。",
                }
                rec.record(
                    "start_examine",
                    args=args,
                    ok=True,
                    summary=f"可开考笔记「{_clip(note.title or str(nid), 40)}」",
                    open_examine=open_payload,
                )
                return out

            cid: UUID | None = UUID(claim_id) if claim_id else None
            if cid is None:
                due = await day_ops.list_due_claims(session, day, user_id=user_id)
                if not due:
                    out = {
                        "ok": False,
                        "action": "open_examine",
                        "error": "今天没有欠账 claim，无法开考。",
                    }
                    rec.record(
                        "start_examine",
                        args=args,
                        ok=False,
                        summary="无欠账可开考",
                    )
                    return out
                cid = due[0].id

            claim_row = await session.get(ClaimRow, cid)
            if claim_row is None or claim_row.user_id != user_id:
                raise KeyError(f"claim not found: {cid}")

            plan = await day_ops.get_plan(session, day, user_id=user_id)
            existing = next((i for i in plan.items if i.claim_id == cid), None)
            if existing is None:
                item = await day_ops.upsert_plan_item(
                    session,
                    day,
                    title=claim_row.text[:500],
                    user_id=user_id,
                    source=PlanItemSource.QUEUE,
                    status=PlanItemStatus.IN_PROGRESS,
                    claim_id=cid,
                    due_at=day,
                )
                plan_item_id = str(item.id)
                plan_changed = True
            else:
                if existing.status != PlanItemStatus.IN_PROGRESS:
                    await day_ops.update_plan_item(
                        session,
                        existing.id,
                        status=PlanItemStatus.IN_PROGRESS,
                        user_id=user_id,
                    )
                    plan_changed = True
                else:
                    plan_changed = False
                plan_item_id = str(existing.id)

            # Soft signal only — does not set mastery / bypass gate.
            if claim_row.status in (
                MasteryStatus.QUEUED.value,
                MasteryStatus.NOT_YET.value,
            ):
                claim_row.status = MasteryStatus.IN_PROGRESS.value
                await session.flush()

            open_payload = {
                "action": "open_examine",
                "claim_id": str(cid),
                "claim_text": _clip(claim_row.text, 160),
                "topic": claim_row.topic,
                "plan_item_id": plan_item_id,
                "plan_changed": plan_changed,
                "thread_id": str(thread_id) if thread_id else None,
            }
            out = {
                **open_payload,
                "ok": True,
                "hint": "可在气泡下点「开考」，或用 claim_id 调用 /v1/examine。",
            }
            rec.record(
                "start_examine",
                args=args,
                ok=True,
                summary=f"可开考：{_clip(claim_row.text, 60)}",
                open_examine=open_payload,
            )
            return out
        except Exception as exc:  # noqa: BLE001
            rec.record(
                "start_examine",
                args=args,
                ok=False,
                summary=f"{type(exc).__name__}: {exc}",
            )
            return {"ok": False, "error": str(exc)}

    async def get_failure_lessons(claim_id: str | None = None) -> dict[str, object]:
        """Read budgeted failure lessons (same claim / confuse neighbors / topic)."""
        args: dict[str, Any] = {"claim_id": claim_id}
        try:
            if claim_id:
                cid = UUID(claim_id)
                claim_row = await session.get(ClaimRow, cid)
                if claim_row is None or claim_row.user_id != user_id:
                    raise KeyError(f"claim not found: {claim_id}")
                block = await day_ops.build_failure_lesson_block(
                    session,
                    user_id=user_id,
                    claim_id=cid,
                    topic=claim_row.topic,
                )
                out: dict[str, object] = {
                    "claim_id": str(cid),
                    "lesson_block": block,
                    "has_lessons": bool(block),
                }
                rec.record(
                    "get_failure_lessons",
                    args=args,
                    ok=True,
                    summary=("有教训摘要" if block else "暂无匹配教训"),
                )
                return out

            entries = await day_ops.list_memory(
                session,
                user_id=user_id,
                kind="failure_digest",
                limit=5,
            )
            digests = [
                {
                    "id": str(e.id),
                    "topic": e.topic,
                    "verdict": e.content.get("verdict"),
                    "claim_text": _clip(str(e.content.get("claim_text") or ""), 80),
                    "follow_up": _clip(str(e.content.get("follow_up") or ""), 80),
                }
                for e in entries
            ]
            listed: dict[str, object] = {
                "count": len(digests),
                "digests": digests,
            }
            rec.record(
                "get_failure_lessons",
                args=args,
                ok=True,
                summary=f"近期失败教训 {len(digests)} 条",
            )
            return listed
        except Exception as exc:  # noqa: BLE001
            rec.record(
                "get_failure_lessons",
                args=args,
                ok=False,
                summary=f"{type(exc).__name__}: {exc}",
            )
            return {"ok": False, "error": str(exc)}

    async def add_memory(note: str, topic: str | None = None) -> dict[str, object]:
        """Write a short long-term note the companion should remember (capped)."""
        text = (note or "").strip()
        args: dict[str, Any] = {"topic": topic, "note_len": len(text)}
        try:
            if not text:
                raise ValueError("note is empty")
            clipped = _clip(text, _MEMORY_NOTE_MAX)
            entry = await day_ops.add_memory(
                session,
                user_id=user_id,
                layer="long",
                kind="note",
                topic=topic,
                content={"text": clipped, "source": "companion_tool"},
                source={
                    "via": "companion_tool",
                    **({"thread_id": str(thread_id)} if thread_id else {}),
                },
            )
            out = {
                "ok": True,
                "id": str(entry.id),
                "topic": entry.topic,
                "text": clipped,
            }
            rec.record(
                "add_memory",
                args=args,
                ok=True,
                summary=f"已记下：{_clip(clipped, 60)}",
            )
            return out
        except Exception as exc:  # noqa: BLE001
            rec.record(
                "add_memory",
                args=args,
                ok=False,
                summary=f"{type(exc).__name__}: {exc}",
            )
            return {"ok": False, "error": str(exc)}

    async def get_upcoming_interview() -> dict[str, object]:
        """Read nearest upcoming interview (7d) with ramp tier + drill suggestion."""
        from datetime import UTC, datetime

        args: dict[str, Any] = {}
        try:
            now = datetime.now(UTC)
            rows = await day_ops.list_upcoming_interviews(
                session, now, user_id=user_id
            )
            if not rows:
                out: dict[str, object] = {
                    "ok": True,
                    "count": 0,
                    "nearest": None,
                    "upcoming": [],
                }
                rec.record(
                    "get_upcoming_interview",
                    args=args,
                    ok=True,
                    summary="近 7 天无面试安排",
                )
                return out
            nearest = rows[0]
            payload = {
                "ok": True,
                "count": len(rows),
                "nearest": nearest.model_dump(mode="json"),
                "upcoming": [r.model_dump(mode="json") for r in rows[:5]],
            }
            rec.record(
                "get_upcoming_interview",
                args=args,
                ok=True,
                summary=(
                    f"{nearest.company} · {nearest.ramp_tier} · "
                    f"约 {nearest.hours_until:.0f}h"
                ),
            )
            return payload
        except Exception as exc:  # noqa: BLE001
            rec.record(
                "get_upcoming_interview",
                args=args,
                ok=False,
                summary=f"{type(exc).__name__}: {exc}",
            )
            return {"ok": False, "error": str(exc)}

    return [
        Tool(
            get_today,
            name="get_today",
            description=(
                "Read today's real plan items and due claims from the database. "
                "Use when the learner asks what they owe today or what's on the plan."
            ),
        ),
        Tool(
            list_due_claims,
            name="list_due_claims",
            description=(
                "List claims currently due for review. "
                "Use for「今天欠什么 / 还欠哪些」without needing the full plan."
            ),
        ),
        Tool(
            start_examine,
            name="start_examine",
            description=(
                "Prepare an open-examine payload for claim_id or note_id "
                "(or first due claim if omitted). Soft-prepares plan only — "
                "does not grade or bypass the mastery gate."
            ),
        ),
        Tool(
            get_failure_lessons,
            name="get_failure_lessons",
            description=(
                "Read budgeted prior failure lessons for a claim, or recent "
                "failure digests if claim_id is omitted."
            ),
        ),
        Tool(
            add_memory,
            name="add_memory",
            description=(
                "Save a short long-term memory note (≤400 chars). "
                "Use only when the learner asks to remember something."
            ),
        ),
        Tool(
            get_upcoming_interview,
            name="get_upcoming_interview",
            description=(
                "Read upcoming real-world interviews (next 7 days) with "
                "countdown ramp_tier and a short project-drill suggestion. "
                "Use for「快面试了 / 下周有面试练什么」."
            ),
        ),
    ]


COMPANION_TOOL_HINT = (
    "【办事工具】你可以调用：get_today、list_due_claims、start_examine、"
    "get_failure_lessons、add_memory、get_upcoming_interview。\n"
    "- 问「今天欠什么 / 今日计划 / 还欠几道」时：先调 get_today 或 list_due_claims，"
    "用真实结果回答，不要编造。\n"
    "- 「帮我开考 / 考我这条」：调 start_examine（可传 claim_id / note_id；"
    "都不传则挑第一条欠账）；告知对方已备好开考，可点气泡下「开考」。"
    "不要假装自己已经判过分——掌握门不在这里。\n"
    "- 「快面试了 / 面试练什么」：调 get_upcoming_interview，用真实日程与 "
    "suggest_action 回答；可引导去顶栏「项目深挖」，不要自动假装已开练。\n"
    "- 需要带着上次教训：get_failure_lessons。\n"
    "- 该记的短教训：add_memory（会截断）。写操作要克制。"
)
