"""Companion builtin tools — whitelist for chat agent tool-calling.

Thin wrappers over ``db.ops`` (same surface REST/MCP use). Lives in ``api/`` so
``gotit.core`` stays free of session / FastAPI / MCP imports. Tool call digests
are recorded for message ``metadata.tool_calls`` (explainable / replayable).

``start_examine`` / ``start_verify`` / ``start_drill`` prepare open-* payloads
(no Critic/gate; do not soft-write claim mastery — plan row may be PLANNED only).
for the Web CTA — they do **not** run Critic, the mastery gate, or Sage.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from gotit.api.action_blocks import owed_blocks_from_claims
from gotit.core.check_routing import route_for_claim
from gotit.core.models import DrillRound, PlanItemSource, PlanItemStatus
from gotit.db import ops as day_ops
from gotit.db.models import ClaimRow, DayNoteRow, InterviewEventRow, LearningDayRow

_MEMORY_NOTE_MAX = 400
_SUMMARY_MAX = 240
_ARGS_DIGEST_MAX = 160
_DUE_LIST_CAP = 12
_VALID_DRILL_ROUNDS = {r.value for r in DrillRound}


@dataclass
class ToolCallRecord:
    name: str
    args_digest: str
    ok: bool
    summary: str
    open_examine: dict[str, object] | None = None
    open_teach: dict[str, object] | None = None
    open_drill: dict[str, object] | None = None
    action_blocks: list[dict[str, object]] | None = None

    def as_dict(self) -> dict[str, object]:
        out: dict[str, object] = {
            "name": self.name,
            "args_digest": self.args_digest,
            "ok": self.ok,
            "summary": self.summary,
        }
        if self.open_examine is not None:
            out["open_examine"] = self.open_examine
        if self.open_teach is not None:
            out["open_teach"] = self.open_teach
        if self.open_drill is not None:
            out["open_drill"] = self.open_drill
        if self.action_blocks:
            out["action_blocks"] = self.action_blocks
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
        open_teach: dict[str, object] | None = None,
        open_drill: dict[str, object] | None = None,
        action_blocks: list[dict[str, object]] | None = None,
    ) -> None:
        self.calls.append(
            ToolCallRecord(
                name=name,
                args_digest=_args_digest(args),
                ok=ok,
                summary=_clip(summary, _SUMMARY_MAX),
                open_examine=open_examine,
                open_teach=open_teach,
                open_drill=open_drill,
                action_blocks=action_blocks,
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

    def last_open_teach(self) -> dict[str, object] | None:
        for call in reversed(self.calls):
            if call.ok and call.open_teach is not None:
                return call.open_teach
        return None

    def last_open_drill(self) -> dict[str, object] | None:
        """Most recent successful open-drill payload in this recorder."""
        for call in reversed(self.calls):
            if call.ok and call.open_drill is not None:
                return call.open_drill
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
    out: dict[str, object] = {
        "id": str(claim.id),
        "text": _clip(claim.text, 120),
        "status": status,
        "topic": claim.topic,
        "next_review_at": (claim.next_review_at.isoformat() if claim.next_review_at else None),
    }
    reason = getattr(claim, "due_reason_text", None)
    if reason:
        out["due_reason_text"] = reason
    code = getattr(claim, "due_reason_code", None)
    if code:
        out["due_reason_code"] = code
    preferred = getattr(claim, "preferred_check_mode", None)
    if preferred is not None:
        out["preferred_check_mode"] = (
            preferred.value if hasattr(preferred, "value") else str(preferred)
        )
    project_id = getattr(claim, "project_id", None)
    if project_id is not None:
        out["project_id"] = str(project_id)
    return out


def _normalize_drill_round(raw: str | None) -> str:
    if raw and str(raw).strip() in _VALID_DRILL_ROUNDS:
        return str(raw).strip()
    return DrillRound.TECH_1.value


async def _build_open_drill(
    session: AsyncSession,
    *,
    user_id: str,
    thread_id: UUID | None,
    round: str | None = None,
    project_id: str | None = None,
    interview_id: str | None = None,
    direction: str | None = None,
) -> tuple[dict[str, object], bool, str]:
    """Return (open_drill payload, has_resume, summary). Pure prepare — no Sage."""
    resume = await day_ops.get_resume(session, user_id=user_id)
    has_resume = resume is not None

    company: str | None = None
    resolved_round = round
    if interview_id:
        row = await session.get(InterviewEventRow, UUID(interview_id))
        if row is None or row.user_id != user_id:
            raise KeyError(f"interview not found: {interview_id}")
        company = row.company
        if not resolved_round:
            resolved_round = row.round

    drill_round = _normalize_drill_round(resolved_round)

    resolved_project_id: UUID | None = UUID(project_id) if project_id else None
    project_name: str | None = None
    if resolved_project_id is not None:
        try:
            proj = await day_ops.get_project(
                session, resolved_project_id, user_id=user_id
            )
            project_name = (proj.name or "").strip() or None
        except KeyError as exc:
            raise KeyError(f"project not found: {project_id}") from exc
    else:
        projects = await day_ops.list_projects(
            session, user_id=user_id, include_archived=False
        )
        if projects:
            resolved_project_id = projects[0].id
            project_name = (projects[0].name or "").strip() or None

    dir_text = (direction or "").strip() or None
    payload: dict[str, object] = {
        "action": "open_drill",
        "round": drill_round,
        "direction": dir_text,
        "project_id": str(resolved_project_id) if resolved_project_id else None,
        "project_name": project_name,
        "interview_id": str(UUID(interview_id)) if interview_id else None,
        "company": company,
        "thread_id": str(thread_id) if thread_id else None,
        "has_resume": has_resume,
    }
    label = company or project_name or drill_round
    summary = f"可深挖：{_clip(str(label), 40)} · {drill_round}"
    if not has_resume:
        summary = "可备深挖，但尚未导入简历"
    return payload, has_resume, summary


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
                    "due_reason_code": it.due_reason_code,
                    "due_reason_text": it.due_reason_text,
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
                "day_closed": view.day_closed,
                "close_suggested": view.close_suggested,
            }
            if view.mastery_snapshot is not None:
                snap = view.mastery_snapshot
                out["mastery_snapshot"] = {
                    "mastered_count": snap.mastered_count,
                    "weak_count": snap.weak_count,
                    "top_due": [_claim_brief(c) for c in snap.top_due],
                    "recent_fails": list(snap.recent_fails),
                }
            if view.close_summary is not None:
                out["close_summary"] = view.close_summary.model_dump(mode="json")
            if view.interview_focus is not None:
                out["interview_focus"] = view.interview_focus.model_dump(mode="json")
            focus_bit = (
                f"，建议深挖 {view.interview_focus.project_name or view.interview_focus.company}"
                if view.interview_focus is not None
                else ""
            )
            rec.record(
                "get_today",
                args=args,
                ok=True,
                summary=(
                    f"{view.date.isoformat()}：计划 {len(view.plan.items)} 条，"
                    f"欠账 {len(view.due_claims)} 条"
                    + ("，已收工" if view.day_closed else "")
                    + focus_bit
                ),
                open_drill=(
                    view.interview_focus.open_drill
                    if view.interview_focus is not None
                    else None
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

    async def close_day(note: str | None = None) -> dict[str, object]:
        """Close today's learning day (idempotent). Does not cancel interviews."""
        args: dict[str, Any] = {
            "day": day.isoformat(),
            "note": (note or "").strip()[:80] or None,
        }
        try:
            summary = await day_ops.close_today(
                session, day, user_id=user_id, note=note
            )
            out: dict[str, object] = {
                "ok": True,
                "day": day.isoformat(),
                "passed_count": summary.passed_count,
                "still_owed_count": summary.still_owed_count,
                "note": summary.note,
                "closed_at": (
                    summary.closed_at.isoformat() if summary.closed_at else None
                ),
            }
            rec.record(
                "close_day",
                args=args,
                ok=True,
                summary=summary.note or (
                    f"收工：过了 {summary.passed_count}，还挂 {summary.still_owed_count}"
                ),
            )
            return out
        except Exception as exc:  # noqa: BLE001
            rec.record(
                "close_day",
                args=args,
                ok=False,
                summary=f"{type(exc).__name__}: {exc}",
            )
            return {"ok": False, "error": str(exc)}

    async def list_due_claims() -> dict[str, object]:
        """List claims due for review today (queued / not_yet / in_progress)."""
        args: dict[str, Any] = {"day": day.isoformat()}
        try:
            today = await day_ops.get_today(session, day, user_id=user_id)
            views = today.due_claims[:_DUE_LIST_CAP]
            claims = [_claim_brief(v) for v in views]
            blocks = owed_blocks_from_claims(views)
            out: dict[str, object] = {
                "date": day.isoformat(),
                "count": len(today.due_claims),
                "claims": claims,
            }
            if blocks:
                out["action_blocks"] = blocks
            rec.record(
                "list_due_claims",
                args=args,
                ok=True,
                summary=f"欠账 {len(today.due_claims)} 条",
                action_blocks=blocks or None,
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

    async def get_ability_state(topic: str | None = None) -> dict[str, object]:
        """Read-only Ability State Projection (per-topic). Does not write mastery."""
        args: dict[str, Any] = {"day": day.isoformat(), "topic": topic}
        try:
            proj = await day_ops.build_ability_state(
                session, user_id=user_id, as_of=day, topic=topic
            )
            out = proj.model_dump(mode="json")
            rec.record(
                "get_ability_state",
                args=args,
                ok=True,
                summary=f"能力态 {len(proj.abilities)} 个 topic",
            )
            return out
        except Exception as exc:  # noqa: BLE001
            rec.record(
                "get_ability_state",
                args=args,
                ok=False,
                summary=f"{type(exc).__name__}: {exc}",
            )
            return {"ok": False, "error": str(exc)}

    async def get_next_action() -> dict[str, object]:
        """State-driven next workflow step. Read-only — does not start verify."""
        args: dict[str, Any] = {"day": day.isoformat()}
        try:
            action = await day_ops.build_next_action(
                session, user_id=user_id, as_of=day
            )
            if action is None:
                out: dict[str, object] = {"action": None, "reason_code": "idle"}
                rec.record(
                    "get_next_action",
                    args=args,
                    ok=True,
                    summary="下一步：空闲",
                )
                return out
            out = action.model_dump(mode="json")
            rec.record(
                "get_next_action",
                args=args,
                ok=True,
                summary=f"下一步：{action.action}（{action.reason_code}）",
            )
            return out
        except Exception as exc:  # noqa: BLE001
            rec.record(
                "get_next_action",
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
                    status=PlanItemStatus.PLANNED,
                    claim_id=cid,
                    due_at=day,
                )
                plan_item_id = str(item.id)
                plan_changed = True
            else:
                plan_changed = False
                plan_item_id = str(existing.id)

            # Prepare only — do not soft-write claim mastery / IN_PROGRESS.
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

    async def start_verify(claim_id: str | None = None) -> dict[str, object]:
        """Prepare open-* by claim preferred_check_mode (form follows claim).

        Soft-prepares plan like start_examine when routing to probe/teach.
        Does not run Critic/gate/Sage.
        """
        args: dict[str, Any] = {
            "claim_id": claim_id,
            "thread_id": str(thread_id) if thread_id else None,
        }
        try:
            cid: UUID | None = UUID(claim_id) if claim_id else None
            if cid is None:
                due = await day_ops.list_due_claims(session, day, user_id=user_id)
                if not due:
                    out: dict[str, object] = {
                        "ok": False,
                        "error": "今天没有欠账 claim，无法开练。",
                    }
                    rec.record(
                        "start_verify",
                        args=args,
                        ok=False,
                        summary="无欠账可开练",
                    )
                    return out
                cid = due[0].id

            claim_row = await session.get(ClaimRow, cid)
            if claim_row is None or claim_row.user_id != user_id:
                raise KeyError(f"claim not found: {cid}")

            route = route_for_claim(
                preferred=claim_row.preferred_check_mode,
                project_id=claim_row.project_id,
            )

            if route.open_key == "open_drill":
                open_payload, _has_resume, summary = await _build_open_drill(
                    session,
                    user_id=user_id,
                    thread_id=thread_id,
                    project_id=str(claim_row.project_id)
                    if claim_row.project_id
                    else None,
                )
                out = {
                    **open_payload,
                    "ok": True,
                    "claim_id": str(cid),
                    "preferred_check_mode": route.mode.value,
                    "hint": "可在气泡下点「练深挖」（练习场，不过门）。",
                }
                rec.record(
                    "start_verify",
                    args=args,
                    ok=True,
                    summary=f"可深挖：{_clip(claim_row.text, 60)}",
                    open_drill=open_payload,
                )
                return out

            # Soft-prepare plan for probe / teach (plan row only; no mastery write).
            plan = await day_ops.get_plan(session, day, user_id=user_id)
            existing = next((i for i in plan.items if i.claim_id == cid), None)
            if existing is None:
                item = await day_ops.upsert_plan_item(
                    session,
                    day,
                    title=claim_row.text[:500],
                    user_id=user_id,
                    source=PlanItemSource.QUEUE,
                    status=PlanItemStatus.PLANNED,
                    claim_id=cid,
                    due_at=day,
                )
                plan_item_id = str(item.id)
                plan_changed = True
            else:
                plan_changed = False
                plan_item_id = str(existing.id)

            if route.open_key == "open_teach":
                open_payload = {
                    "action": "open_teach",
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
                    "preferred_check_mode": route.mode.value,
                    "hint": "可在气泡下点「回讲」，或用 claim_id 调用 /v1/teach。",
                }
                rec.record(
                    "start_verify",
                    args=args,
                    ok=True,
                    summary=f"可回讲：{_clip(claim_row.text, 60)}",
                    open_teach=open_payload,
                )
                return out

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
                "preferred_check_mode": route.mode.value,
                "hint": "可在气泡下点「开考」，或用 claim_id 调用 /v1/examine。",
            }
            rec.record(
                "start_verify",
                args=args,
                ok=True,
                summary=f"可开考：{_clip(claim_row.text, 60)}",
                open_examine=open_payload,
            )
            return out
        except Exception as exc:  # noqa: BLE001
            rec.record(
                "start_verify",
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
        """Read nearest upcoming interview (7d) with ramp tier + open_drill CTA."""
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
            open_drill, _has_resume, _sum = await _build_open_drill(
                session,
                user_id=user_id,
                thread_id=thread_id,
                round=nearest.round,
                project_id=str(nearest.project_id) if nearest.project_id else None,
                interview_id=str(nearest.interview_id),
            )
            payload = {
                "ok": True,
                "count": len(rows),
                "nearest": nearest.model_dump(mode="json"),
                "upcoming": [r.model_dump(mode="json") for r in rows[:5]],
                "open_drill": open_drill,
            }
            rec.record(
                "get_upcoming_interview",
                args=args,
                ok=True,
                summary=(
                    f"{nearest.company} · {nearest.ramp_tier} · "
                    f"约 {nearest.hours_until:.0f}h"
                ),
                open_drill=open_drill,
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

    async def start_drill(
        round: str | None = None,
        project_id: str | None = None,
        interview_id: str | None = None,
        direction: str | None = None,
    ) -> dict[str, object]:
        """Prepare an open-drill payload. Does not create a session or run Sage."""
        args: dict[str, Any] = {
            "round": round,
            "project_id": project_id,
            "interview_id": interview_id,
            "direction": direction,
            "thread_id": str(thread_id) if thread_id else None,
        }
        try:
            open_payload, has_resume, summary = await _build_open_drill(
                session,
                user_id=user_id,
                thread_id=thread_id,
                round=round,
                project_id=project_id,
                interview_id=interview_id,
                direction=direction,
            )
            out: dict[str, object] = {
                **open_payload,
                "ok": True,
                "hint": (
                    "可在气泡下点「练深挖」开练（练习场，不过门）；尚未导入简历时会提示先导入。"
                    if has_resume
                    else "请先导入简历，再点气泡下「练深挖」。"
                ),
            }
            rec.record(
                "start_drill",
                args=args,
                ok=True,
                summary=summary,
                open_drill=open_payload,
            )
            return out
        except Exception as exc:  # noqa: BLE001
            rec.record(
                "start_drill",
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
            close_day,
            name="close_day",
            description=(
                "Close today's learning day (idempotent). "
                "Use when the learner says they're done for today / 收工. "
                "Does not cancel interviews or block manual practice."
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
            get_ability_state,
            name="get_ability_state",
            description=(
                "Read Ability State Projection by topic (mastered / pending / "
                "weak points / recent trend). Read-only — does not write mastery. "
                "Use for「我某方面怎么样 / 哪些能力还弱」."
            ),
        ),
        Tool(
            get_next_action,
            name="get_next_action",
            description=(
                "Decide the learner's next step from owed / ability / interview "
                "state (examine|review|teach|drill|calibrate). Read-only — does "
                "not start a verify run. Use for「我接下来该练什么」."
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
            start_verify,
            name="start_verify",
            description=(
                "Prepare the right open-* for a claim by preferred_check_mode "
                "(开考 / 回讲 / 深挖). Prefer this over start_examine when the "
                "learner says「帮我开练」without specifying the form. Soft-prepare "
                "only — does not grade or bypass the mastery gate."
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
                "countdown ramp_tier and an open_drill payload for one-tap drill. "
                "Use for「快面试了 / 下周有面试练什么」."
            ),
        ),
        Tool(
            start_drill,
            name="start_drill",
            description=(
                "Prepare an open-drill payload (round / project / interview). "
                "Does not create a drill session or run Sage — the learner "
                "taps「练深挖」in the bubble to start (practice; not mastery)."
            ),
        ),
    ]


COMPANION_TOOL_HINT = (
    "【办事工具】你可以调用：get_today、list_due_claims、get_ability_state、"
    "get_next_action、start_examine、"
    "start_verify、get_failure_lessons、add_memory、get_upcoming_interview、"
    "start_drill、close_day。\n"
    "- 问「今天欠什么 / 今日计划 / 还欠几道」时：先调 get_today 或 list_due_claims，"
    "用真实结果回答，不要编造。\n"
    "- 问「某能力怎么样 / 哪块还弱」：调 get_ability_state（只读投影，不是第二套权威）。\n"
    "- 问「接下来练什么 / 该开考还是摸底」：调 get_next_action（状态驱动，不是固定剧本）。\n"
    "- 「帮我开练 / 练这条」：优先调 start_verify（按 claim 偏好分流开考/回讲/深挖）。\n"
    "- 「帮我开考 / 考我这条」：调 start_examine（可传 claim_id / note_id；"
    "都不传则挑第一条欠账）；告知对方已备好开考，可点气泡下「开考」。"
    "不要假装自己已经判过分——掌握门不在这里。\n"
    "- 「今天收工 / 可以停了」：调 close_day；用返回的 note / 计数说一句短复盘，"
    "不要羞辱还挂着的题；收工后仍可手动开练。\n"
    "- 「快面试了 / 面试练什么」：调 get_upcoming_interview；需要开练时再调 "
    "start_drill（可传 interview_id / round / project_id）。"
    "告知可点气泡下「练深挖」（练习场，不过门），"
    "不要假装已经开练或判过分。\n"
    "- 需要带着上次教训：get_failure_lessons。\n"
    "- 该记的短教训：add_memory（会截断）。写操作要克制。"
)
