from __future__ import annotations

from datetime import date
from pathlib import Path
from uuid import UUID, uuid4

import anyio
from mcp.server.fastmcp import FastMCP
from sqlalchemy.ext.asyncio import AsyncSession

from gotit import __version__
from gotit.api.deps import (
    SessionMemoryReader,
    SessionPromptReader,
    get_critic_model,
    get_model,
    resolve_critic_binding,
)
from gotit.api.settings import Settings, get_settings
from gotit.api.workflow_persist import (
    drill_agent_text,
    examine_agent_text,
    persist_workflow_exchange,
    teach_agent_text,
)
from gotit.core.agents.axiom import (
    build_axiom_agent,
    build_topic_axiom_agent,
    run_axiom,
    run_topic_examine,
    stub_topic_examine,
)
from gotit.core.agents.compass import build_compass_agent, run_compass
from gotit.core.agents.echo import build_echo_agent, run_echo
from gotit.core.agents.sage import build_sage_agent, run_sage, stub_sage
from gotit.core.models import (
    DrillMaterial,
    DrillRound,
    InterviewStatus,
    MasteryStatus,
    PlanItemSource,
    PlanItemStatus,
    Project,
    ProjectStatus,
    ResumeDocument,
    SageVerdict,
    TeachVerdict,
)
from gotit.core.resume.extract import extract_text
from gotit.core.resume.parse import (
    build_resume_parser,
    load_resume_system_prompt,
    run_resume_parser,
    stub_parse,
)
from gotit.db import ops as day_ops
from gotit.db import session_scope
from gotit.db.models import ClaimRow, DayNoteRow
from gotit.db.runtime import ensure_db

mcp = FastMCP("gotit")


def _user_id() -> str:
    return get_settings().gotit_user_id


@mcp.tool()
def gotit_health() -> dict[str, str]:
    """Return gotit-ai service health and version."""
    return {"status": "ok", "version": __version__}


@mcp.tool()
async def gotit_ingest(material: str) -> dict[str, object]:
    """Ingest study material and return stub claims (Librarian not wired yet)."""
    await ensure_db()
    claim = day_ops.stub_extract_claim(material)
    async with session_scope() as session:
        session.add(
            ClaimRow(
                id=claim.id,
                user_id=_user_id(),
                text=claim.text,
                source_excerpt=claim.source_excerpt,
                status=claim.status.value,
                source_note_id=None,
                next_review_at=None,
            )
        )
    return {
        "claims": [claim.model_dump(mode="json")],
        "state": "claim",
        "note": "stub: claim extraction not wired yet",
    }


@mcp.tool()
async def gotit_examine(
    claim_id: str | None = None,
    topic: str | None = None,
    note_id: str | None = None,
    answer: str | None = None,
    history: list[dict[str, str]] | None = None,
    verdict: str | None = None,
    thread_id: str | None = None,
) -> dict[str, object]:
    """Examine a claim (multi-turn). Pass `note_id` for note-session mode or
    `topic` for topic-session mode (Axiom shuttles across the claims); pass
    `verdict` to bypass the agent (stub/tests, single-claim mode only).
    Optional `thread_id` appends turns to the companion thread stream."""
    await ensure_db()
    user_id = _user_id()
    tid = UUID(thread_id) if thread_id else None

    async def _persist(
        *,
        agent_text: str,
        extra: dict[str, object],
    ) -> dict[str, object] | None:
        if tid is None:
            return None
        try:
            await persist_workflow_exchange(
                thread_id=tid,
                user_id=user_id,
                workflow="examine",
                agent_text=agent_text,
                user_text=answer,
                extra_metadata=extra,
            )
        except KeyError as exc:
            return {"error": str(exc)}
        return None

    # --- Claims-session mode (note_id or topic) ---
    if note_id is not None or topic is not None:
        async with session_scope() as session:
            if note_id is not None:
                claims = await day_ops.list_note_claims(
                    session, UUID(note_id), user_id=user_id
                )
            elif topic is not None:
                claims = await day_ops.list_topic_claims_today(
                    session, topic, user_id=user_id
                )
        if not get_settings().llm_api_key:
            session_result = stub_topic_examine(
                claims=claims, answer=answer, history=history
            )
        else:
            async with session_scope() as session:
                from gotit.db.ops.memory import build_failure_lesson_block

                lesson_block: str | None = None
                if claims:
                    focus = claims[0]
                    lesson_block = await build_failure_lesson_block(
                        session,
                        user_id=user_id,
                        claim_id=focus.id,
                        topic=topic or focus.topic,
                        neighbor_claim_ids=[c.id for c in claims[1:]],
                    )
                prompt = await SessionPromptReader(session).get_active_prompt("axiom")
                system_prompt = prompt.system_prompt if prompt else ""
                reader = SessionMemoryReader(session, user_id=user_id)
                claims_agent = build_topic_axiom_agent(
                    get_model(), system_prompt=system_prompt
                )
            session_result = await run_topic_examine(
                claims_agent,
                reader,
                topic=topic or "",
                claims=claims,
                history=history or [],
                answer=answer,
                failure_lesson_block=lesson_block,
            )
        writeback: dict[str, object] | None = None
        if (
            session_result.done
            and session_result.verdict is not None
            and session_result.current_claim_id
        ):
            async with session_scope() as session:
                writeback = await day_ops.apply_examine_verdict(
                    session,
                    session_result.current_claim_id,
                    verdict=session_result.verdict,
                    user_id=user_id,
                )
        extra: dict[str, object] = {"session_done": session_result.session_done}
        if note_id is not None:
            extra["note_id"] = note_id
        if topic is not None:
            extra["topic"] = topic
        if session_result.current_claim_id:
            extra["claim_id"] = str(session_result.current_claim_id)
        if session_result.verdict:
            extra["verdict"] = session_result.verdict
        err = await _persist(
            agent_text=examine_agent_text(
                follow_up=session_result.follow_up,
                done=session_result.done,
                verdict=session_result.verdict,
            ),
            extra=extra,
        )
        if err:
            return err
        return {
            "verdict": session_result.model_dump(mode="json"),
            "writeback": writeback,
        }

    # --- Single-claim mode ---
    if claim_id is None:
        return {"error": "one of `note_id`, `topic`, or `claim_id` is required"}

    if verdict is not None:
        async with session_scope() as session:
            direct_writeback = await day_ops.apply_examine_verdict(
                session, UUID(claim_id), verdict=verdict, user_id=user_id
            )
        err = await _persist(
            agent_text=examine_agent_text(follow_up="", done=True, verdict=verdict),
            extra={
                "claim_id": claim_id,
                "verdict": verdict,
                "session_done": True,
            },
        )
        if err:
            return err
        return {
            "verdict": {
                "done": True,
                "verdict": verdict,
                "score": None,
                "evidence": None,
                "follow_up": "",
            },
            "writeback": direct_writeback,
        }

    async with session_scope() as session:
        claim = await session.get(ClaimRow, UUID(claim_id))
        if claim is None or claim.user_id != user_id:
            return {"error": f"claim not found: {claim_id}"}
        from gotit.db.ops.memory import build_failure_lesson_block

        lesson_block = await build_failure_lesson_block(
            session,
            user_id=user_id,
            claim_id=UUID(claim_id),
            topic=claim.topic,
        )
        prompt = await SessionPromptReader(session).get_active_prompt("axiom")
        system_prompt = prompt.system_prompt if prompt else ""
        reader = SessionMemoryReader(session, user_id=user_id)
        agent = build_axiom_agent(get_model(), system_prompt=system_prompt)
        result = await run_axiom(
            agent,
            reader,
            claim_text=claim.text,
            history=history or [],
            answer=answer,
            failure_lesson_block=lesson_block,
        )

    writeback = None
    if result.done and result.verdict is not None:
        async with session_scope() as session:
            writeback = await day_ops.apply_examine_verdict(
                session, UUID(claim_id), verdict=result.verdict, user_id=user_id
            )
    err = await _persist(
        agent_text=examine_agent_text(
            follow_up=result.follow_up,
            done=result.done,
            verdict=result.verdict,
        ),
        extra={
            "claim_id": claim_id,
            **({"verdict": result.verdict} if result.verdict else {}),
            "session_done": bool(result.done),
        },
    )
    if err:
        return err
    return {"verdict": result.model_dump(mode="json"), "writeback": writeback}


@mcp.tool()
async def gotit_today(day: str | None = None) -> dict[str, object]:
    """Aggregate today's plan, truncated notes, and due claims."""
    await ensure_db()
    target = date.fromisoformat(day) if day else None
    async with session_scope() as session:
        view = await day_ops.get_today(session, target, user_id=_user_id())
    return view.model_dump(mode="json")


@mcp.tool()
async def gotit_get_plan(day: str) -> dict[str, object]:
    """Get the learning plan for a YYYY-MM-DD day."""
    await ensure_db()
    async with session_scope() as session:
        view = await day_ops.get_plan(session, date.fromisoformat(day), user_id=_user_id())
    return view.model_dump(mode="json")


@mcp.tool()
async def gotit_upsert_plan_item(
    day: str,
    title: str,
    item_id: str | None = None,
    source: str = PlanItemSource.MANUAL.value,
    status: str = PlanItemStatus.PLANNED.value,
    claim_id: str | None = None,
    sort_order: int | None = None,
    due_at: str | None = None,
    due_time: str | None = None,
) -> dict[str, object]:
    """Create or update a plan item. Pass due_time=HH:MM when known (Reminders).

    Best-effort syncs to Apple Reminders after write (same Mac as OpenClaw).
    """
    await ensure_db()
    day_d = date.fromisoformat(day)
    async with session_scope() as session:
        view = await day_ops.upsert_plan_item(
            session,
            day_d,
            title=title,
            user_id=_user_id(),
            item_id=UUID(item_id) if item_id else None,
            source=PlanItemSource(source),
            status=PlanItemStatus(status),
            claim_id=UUID(claim_id) if claim_id else None,
            sort_order=sort_order,
            due_at=date.fromisoformat(due_at) if due_at else None,
            due_time=due_time,
        )
    from gotit.bridge.reminders import push_day

    apple_err = push_day(day_d, title=view.title, time=view.due_time)
    out = view.model_dump(mode="json")
    if apple_err:
        out["apple_sync_error"] = apple_err
    else:
        out["apple_synced"] = True
    return out


@mcp.tool()
async def gotit_fill_today_from_queue(day: str | None = None) -> dict[str, object]:
    """Fill the day's plan from due / not-yet claims."""
    await ensure_db()
    target = date.fromisoformat(day) if day else date.today()
    async with session_scope() as session:
        view = await day_ops.fill_today_from_queue(session, target, user_id=_user_id())
    return view.model_dump(mode="json")


@mcp.tool()
async def gotit_update_plan_item(
    item_id: str,
    title: str | None = None,
    status: str | None = None,
    sort_order: int | None = None,
    due_at: str | None = None,
    due_time: str | None = None,
    defer_to: str | None = None,
) -> dict[str, object]:
    """Patch a plan item (status, defer, reorder, due_time). Syncs Reminders for the day."""
    await ensure_db()
    plan_day: date | None = None
    async with session_scope() as session:
        view = await day_ops.update_plan_item(
            session,
            UUID(item_id),
            title=title,
            status=PlanItemStatus(status) if status else None,
            sort_order=sort_order,
            due_at=date.fromisoformat(due_at) if due_at else None,
            due_time=due_time,
            defer_to=date.fromisoformat(defer_to) if defer_to else None,
            user_id=_user_id(),
        )
        from gotit.db.models import LearningDayRow, PlanItemRow

        row = await session.get(PlanItemRow, UUID(item_id))
        if row is not None:
            day_row = await session.get(LearningDayRow, row.day_id)
            if day_row is not None:
                plan_day = day_row.day
    out = view.model_dump(mode="json")
    if plan_day is not None:
        from gotit.bridge.reminders import push_day

        apple_err = push_day(plan_day, reconcile=True)
        if apple_err:
            out["apple_sync_error"] = apple_err
        else:
            out["apple_synced"] = True
    return out


@mcp.tool()
async def gotit_delete_plan_item(
    item_id: str | None = None,
    day: str | None = None,
    title: str | None = None,
) -> dict[str, object]:
    """Delete a plan item by id, or by day + title (casefold exact match).

    Also removes the matching incomplete Reminder (best-effort).
    """
    await ensure_db()
    uid = _user_id()
    async with session_scope() as session:
        matched_title = (title or "").strip() or None
        matched_day = day
        if item_id:
            target_id = UUID(item_id)
            from gotit.db.models import LearningDayRow, PlanItemRow

            row = await session.get(PlanItemRow, target_id)
            if row is not None:
                matched_title = row.title
                day_row = await session.get(LearningDayRow, row.day_id)
                if day_row is not None:
                    matched_day = day_row.day.isoformat()
        else:
            if not day or not matched_title:
                raise ValueError("provide item_id, or both day and title")
            plan = await day_ops.get_plan(
                session, date.fromisoformat(day), user_id=uid
            )
            needle = matched_title.casefold()
            hits = [
                i for i in plan.items if (i.title or "").strip().casefold() == needle
            ]
            if not hits:
                raise KeyError(f"plan item not found: day={day} title={title!r}")
            if len(hits) > 1:
                ids = ", ".join(str(h.id) for h in hits)
                raise ValueError(
                    f"multiple plan items match title={title!r} on {day}; "
                    f"pass item_id explicitly ({ids})"
                )
            target_id = hits[0].id
            matched_title = hits[0].title
        await day_ops.delete_plan_item(session, target_id, user_id=uid)
    out: dict[str, object] = {
        "ok": True,
        "deleted_id": str(target_id),
        "day": matched_day,
        "title": matched_title,
    }
    if matched_title and matched_day:
        from gotit.bridge.reminders import rm_item

        apple_err = rm_item(date.fromisoformat(matched_day), matched_title)
        if apple_err:
            out["apple_sync_error"] = apple_err
        else:
            out["apple_synced"] = True
    return out


@mcp.tool()
async def gotit_list_notes(day: str) -> list[dict[str, object]]:
    """List notes for a day (bodies truncated to excerpts)."""
    await ensure_db()
    async with session_scope() as session:
        notes = await day_ops.list_notes(
            session,
            date.fromisoformat(day),
            user_id=_user_id(),
            full_body=False,
        )
    return [n.model_dump(mode="json") for n in notes]


@mcp.tool()
async def gotit_list_all_notes() -> list[dict[str, object]]:
    """List all notes across days (newest first, bodies truncated to excerpts)."""
    await ensure_db()
    async with session_scope() as session:
        notes = await day_ops.list_all_notes(session, user_id=_user_id())
    return [n.model_dump(mode="json") for n in notes]


@mcp.tool()
async def gotit_add_note(
    day: str,
    body: str,
    title: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, object]:
    """Add a study note for a day."""
    await ensure_db()
    async with session_scope() as session:
        note = await day_ops.add_note(
            session,
            date.fromisoformat(day),
            body,
            title=title,
            tags=tags,
            user_id=_user_id(),
        )
    return note.model_dump(mode="json")


@mcp.tool()
async def gotit_ingest_note(note_id: str, add_plan_item: bool = True) -> dict[str, object]:
    """Ingest a stored note into claims (Compass when LLM configured, else stub)."""
    await ensure_db()
    user_id = _user_id()
    settings = get_settings()
    claims = None

    if settings.llm_api_key:
        async with session_scope() as session:
            note = await session.get(DayNoteRow, UUID(note_id))
            if note is None:
                return {"error": f"note not found: {note_id}"}
            prompt = await SessionPromptReader(session).get_active_prompt("compass")
            system_prompt = prompt.system_prompt if prompt else ""
            reader = SessionMemoryReader(session, user_id=user_id)
            agent = build_compass_agent(get_model(), system_prompt=system_prompt)
            output = await run_compass(agent, reader, note_body=note.body)
        from gotit.core.models import Claim

        claims = [
            Claim(
                text=c.text,
                source_excerpt=note.body[:200],
                status=MasteryStatus.NOT_YET,
                source_note_id=UUID(note_id),
                topic=c.topic,
                tags=list(c.tags),
            )
            for c in output.claims
        ]

    async with session_scope() as session:
        return await day_ops.ingest_note(
            session,
            UUID(note_id),
            claims=claims,
            user_id=user_id,
            add_plan_item=add_plan_item,
        )


@mcp.tool()
async def gotit_delete_notes(note_ids: list[str]) -> dict[str, object]:
    """Delete one or more notes by id. Skips unknown ids. Returns {deleted: n}."""
    await ensure_db()
    ids = [UUID(x) for x in note_ids]
    async with session_scope() as session:
        deleted = await day_ops.delete_notes(session, ids, user_id=_user_id())
    return {"deleted": deleted}


@mcp.tool()
async def gotit_curate(day: str, claim_texts: list[str]) -> dict[str, object]:
    """Add plan items for recommended claims (matched by text) for the day."""
    await ensure_db()
    async with session_scope() as session:
        view = await day_ops.curate_claims(
            session,
            date.fromisoformat(day),
            claim_texts=claim_texts,
            user_id=_user_id(),
        )
    return view.model_dump(mode="json")


@mcp.tool()
async def gotit_teach(
    topic: str,
    answer: str | None = None,
    history: list[dict[str, str]] | None = None,
    you_taught_well: bool | None = None,
    thread_id: str | None = None,
) -> dict[str, object]:
    """Teach-back mode (Echo). Pass `you_taught_well` to bypass the agent (stub/tests).
    Optional `thread_id` appends turns to the companion thread stream."""
    await ensure_db()
    user_id = _user_id()
    tid = UUID(thread_id) if thread_id else None

    async def _persist(verdict: TeachVerdict) -> dict[str, object] | None:
        if tid is None:
            return None
        extra: dict[str, object] = {"topic": topic, "session_done": verdict.done}
        if verdict.you_taught_well is not None:
            extra["verdict"] = "passed" if verdict.you_taught_well else "owe_next"
        try:
            await persist_workflow_exchange(
                thread_id=tid,
                user_id=user_id,
                workflow="teach",
                agent_text=teach_agent_text(
                    done=verdict.done,
                    you_taught_well=verdict.you_taught_well,
                    gaps=list(verdict.gaps),
                    next_question=verdict.next_question,
                ),
                user_text=answer,
                extra_metadata=extra,
            )
        except KeyError as exc:
            return {"error": str(exc)}
        return None

    if you_taught_well is not None:
        verdict = TeachVerdict(
            done=True,
            you_taught_well=you_taught_well,
            gaps=[],
            next_question=None,
        )
        err = await _persist(verdict)
        if err:
            return err
        return {"verdict": verdict.model_dump(mode="json")}

    async with session_scope() as session:
        prompt = await SessionPromptReader(session).get_active_prompt("echo")
        system_prompt = prompt.system_prompt if prompt else ""
        reader = SessionMemoryReader(session, user_id=user_id)
        agent = build_echo_agent(get_model(), system_prompt=system_prompt)
        verdict = await run_echo(
            agent,
            reader,
            topic=topic,
            history=history or [],
            answer=answer,
        )
    err = await _persist(verdict)
    if err:
        return err
    return {"verdict": verdict.model_dump(mode="json")}


@mcp.tool()
async def gotit_list_memory(
    layer: str | None = None,
    kind: str | None = None,
    topic: str | None = None,
    limit: int = 50,
) -> list[dict[str, object]]:
    """List memory entries (filtered by layer/kind/topic)."""
    await ensure_db()
    async with session_scope() as session:
        entries = await day_ops.list_memory(
            session,
            user_id=_user_id(),
            layer=layer,
            kind=kind,
            topic=topic,
            limit=limit,
        )
    return [e.model_dump(mode="json") for e in entries]


@mcp.tool()
async def gotit_add_memory(
    layer: str,
    kind: str,
    content: dict[str, object] | None = None,
    topic: str | None = None,
    source: dict[str, object] | None = None,
) -> dict[str, object]:
    """Add a memory entry (long/working/session)."""
    await ensure_db()
    async with session_scope() as session:
        entry = await day_ops.add_memory(
            session,
            user_id=_user_id(),
            layer=layer,
            kind=kind,
            content=content or {},
            topic=topic,
            source=source,
        )
    return entry.model_dump(mode="json")


@mcp.tool()
async def gotit_list_pending_failure_digests(limit: int = 20) -> list[dict[str, object]]:
    """Pending examine failure digests (almost|owe_next) not yet sent to WeChat."""
    await ensure_db()
    async with session_scope() as session:
        entries = await day_ops.list_pending_failure_digests(
            session, user_id=_user_id(), limit=limit
        )
    return [e.model_dump(mode="json") for e in entries]


@mcp.tool()
async def gotit_mark_failure_digest_notified(memory_id: str) -> dict[str, object]:
    """Mark a failure_digest memory as delivered (WeChat)."""
    await ensure_db()
    async with session_scope() as session:
        entry = await day_ops.mark_failure_digest_notified(
            session, UUID(memory_id), user_id=_user_id()
        )
    return entry.model_dump(mode="json")


@mcp.tool()
async def gotit_record_shell_event(
    job: str,
    items: list[dict[str, object]] | None = None,
    due_summary: list[str] | None = None,
    errors: list[str] | None = None,
    delivery_ok: bool | None = None,
    channel: str = "openclaw-weixin",
    skill: str = "digest",
    run_id: str | None = None,
    subject: str | None = None,
    day: str | None = None,
) -> dict[str, object]:
    """Record an OpenClaw plan/news push as kind=shell_event (obs truth)."""
    await ensure_db()
    async with session_scope() as session:
        entry = await day_ops.record_shell_event(
            session,
            user_id=_user_id(),
            job=job,
            items=items,
            due_summary=due_summary,
            errors=errors,
            delivery_ok=delivery_ok,
            channel=channel,
            skill=skill,
            run_id=run_id,
            subject=subject,
            day=day,
        )
    return entry.model_dump(mode="json")


@mcp.tool()
async def gotit_record_interest(
    event_id: str,
    item_index: int,
    title: str,
    link: str | None = None,
    feed_id: str | None = None,
    topic: str | None = None,
    channel: str = "openclaw-weixin",
    skill: str = "digest",
) -> dict[str, object]:
    """Record 「这篇有用」 as kind=interest (no ingest)."""
    await ensure_db()
    async with session_scope() as session:
        entry = await day_ops.record_interest(
            session,
            user_id=_user_id(),
            event_id=event_id,
            item_index=item_index,
            title=title,
            link=link,
            feed_id=feed_id,
            topic=topic,
            channel=channel,
            skill=skill,
        )
    return entry.model_dump(mode="json")


@mcp.tool()
async def gotit_list_shell_activity(
    kinds: str | None = None,
    limit: int = 50,
) -> list[dict[str, object]]:
    """List shell_event / interest activity (comma kinds, newest first)."""
    await ensure_db()
    kind_list = [k.strip() for k in kinds.split(",")] if kinds else None
    async with session_scope() as session:
        entries = await day_ops.list_shell_activity(
            session,
            user_id=_user_id(),
            kinds=kind_list,
            limit=limit,
        )
    return [e.model_dump(mode="json") for e in entries]


@mcp.tool()
async def gotit_get_digest_prefs() -> dict[str, object]:
    """Get OpenClaw digest prefs (plan cron + optional AI/YouTube feeds)."""
    await ensure_db()
    async with session_scope() as session:
        prefs = await day_ops.get_digest_prefs(session, user_id=_user_id())
    return prefs.model_dump(mode="json")


@mcp.tool()
async def gotit_put_digest_prefs(prefs: dict[str, object]) -> dict[str, object]:
    """Replace digest prefs (feeds, cron strings, news switch, keywords)."""
    from gotit.core.models import DigestPrefs

    await ensure_db()
    body = DigestPrefs.model_validate(prefs)
    async with session_scope() as session:
        saved = await day_ops.put_digest_prefs(session, body, user_id=_user_id())
    return saved.model_dump(mode="json")


@mcp.tool()
async def gotit_sync_digest_cron() -> dict[str, object]:
    """Re-register OpenClaw plan/news cron from current digest_prefs (install-cron.sh)."""
    result = day_ops.sync_digest_openclaw_cron()
    return result.model_dump(mode="json")


@mcp.tool()
async def gotit_obs_profile() -> dict[str, object]:
    """Profile v0: trajectory + interest aggregates by topic."""
    await ensure_db()
    async with session_scope() as session:
        view = await day_ops.build_profile_v0(session, user_id=_user_id())
    return view.model_dump(mode="json")


@mcp.tool()
async def gotit_obs_graph() -> dict[str, object]:
    """Graph v0: claim–topic–project edges; interest→topic only."""
    await ensure_db()
    async with session_scope() as session:
        view = await day_ops.build_graph_v0(session, user_id=_user_id())
    return view.model_dump(mode="json")


@mcp.tool()
async def gotit_list_prompts(
    agent_name: str | None = None,
    active_only: bool = False,
) -> list[dict[str, object]]:
    """List prompt versions (optionally filtered)."""
    await ensure_db()
    async with session_scope() as session:
        versions = await day_ops.list_prompts(
            session,
            agent_name=agent_name,
            active_only=active_only,
        )
    return [v.model_dump(mode="json") for v in versions]


@mcp.tool()
async def gotit_register_prompts() -> list[dict[str, object]]:
    """Load prompts/*.md into the database and mark the newest per agent active."""
    from pathlib import Path

    from gotit.prompts import load_prompt_dir

    await ensure_db()
    versions = load_prompt_dir(Path("prompts"))
    async with session_scope() as session:
        registered = await day_ops.register_prompts(session, versions)
    return [v.model_dump(mode="json") for v in registered]


# --- Project drill ---


@mcp.tool()
async def gotit_list_projects(include_archived: bool = False) -> list[dict[str, object]]:
    """List the learner's projects (active by default)."""
    await ensure_db()
    async with session_scope() as session:
        projects = await day_ops.list_projects(
            session, user_id=_user_id(), include_archived=include_archived
        )
    return [p.model_dump(mode="json") for p in projects]


@mcp.tool()
async def gotit_get_project(project_id: str) -> dict[str, object]:
    """Get a single project by id."""
    await ensure_db()
    async with session_scope() as session:
        project = await day_ops.get_project(
            session, UUID(project_id), user_id=_user_id()
        )
    return project.model_dump(mode="json")


@mcp.tool()
async def gotit_update_project(
    project_id: str,
    name: str | None = None,
    role: str | None = None,
    goal: str | None = None,
    tech_stack: list[str] | None = None,
    status: str | None = None,
) -> dict[str, object]:
    """Update a project's fields. Set status='archived' to archive."""
    await ensure_db()
    async with session_scope() as session:
        project = await day_ops.update_project(
            session,
            UUID(project_id),
            user_id=_user_id(),
            name=name,
            role=role,
            goal=goal,
            tech_stack=tech_stack,
            status=ProjectStatus(status) if status else None,
        )
    return project.model_dump(mode="json")


@mcp.tool()
async def gotit_delete_project(project_id: str) -> dict[str, object]:
    """Archive a project (soft-delete); it leaves the default library list."""
    await ensure_db()
    async with session_scope() as session:
        project = await day_ops.archive_project(
            session, UUID(project_id), user_id=_user_id()
        )
    return project.model_dump(mode="json")


@mcp.tool()
async def gotit_project_progress(project_id: str) -> dict[str, object]:
    """Return claim mastery progress for a project."""
    await ensure_db()
    async with session_scope() as session:
        progress = await day_ops.project_progress(
            session, UUID(project_id), user_id=_user_id()
        )
    return progress.model_dump(mode="json")


@mcp.tool()
async def gotit_upload_resume(file_path: str) -> dict[str, object]:
    """Upload a resume file (local path), extract text + parse to ResumeDocument.

    MCP stdio cannot pass multipart; OpenClaw downloads the file and passes a
    local path. Returns {upload_id, file_path, document}.
    """
    await ensure_db()
    settings = get_settings()
    path = Path(file_path)
    content = path.read_bytes()
    if len(content) > 10 * 1024 * 1024:
        raise ValueError("resume file too large (max 10MB)")
    content_type = _resume_content_type(path)
    upload_id = uuid4()
    ext = _resume_ext(content_type)
    stored = f"uploads/{upload_id}.{ext}"
    Path(stored).parent.mkdir(parents=True, exist_ok=True)
    Path(stored).write_bytes(content)
    resume_text = extract_text(content, content_type)
    if not settings.llm_api_key:
        out = stub_parse(upload_id=upload_id, resume_text=resume_text)
    else:
        system_prompt = load_resume_system_prompt()
        agent = build_resume_parser(get_model(), system_prompt=system_prompt)
        out = await run_resume_parser(agent, upload_id=upload_id, resume_text=resume_text)
    return {
        "upload_id": str(upload_id),
        "file_path": stored,
        "document": out.document.model_dump(mode="json"),
    }


@mcp.tool()
async def gotit_apply_resume(
    upload_id: str,
    document: dict[str, object],
    ingest: bool = False,
    file_path: str | None = None,
) -> dict[str, object]:
    """Apply an (edited) parsed resume: clear-rebuild projects (no quiz notes)."""
    await ensure_db()
    doc = ResumeDocument.model_validate(document)
    resolved = file_path
    if not resolved or not Path(resolved).exists():
        candidates = sorted(Path("uploads").glob(f"{upload_id}.*"))
        if candidates:
            resolved = str(candidates[0])
        elif file_path:
            resolved = file_path
        else:
            resolved = f"uploads/{upload_id}"
    async with session_scope() as session:
        return await day_ops.apply_resume(
            session,
            doc,
            upload_id=UUID(upload_id),
            file_path=resolved,
            ingest=ingest,
            user_id=_user_id(),
        )


@mcp.tool()
async def gotit_get_resume() -> dict[str, object] | None:
    """Return the current global resume record (or null if none)."""
    await ensure_db()
    async with session_scope() as session:
        rec = await day_ops.get_resume(session, user_id=_user_id())
    return rec.model_dump(mode="json") if rec else None


@mcp.tool()
async def gotit_list_drill_materials() -> list[dict[str, object]]:
    """List all deep-dive materials for the user."""
    await ensure_db()
    async with session_scope() as session:
        mats = await day_ops.list_drill_materials(session, user_id=_user_id())
    return [m.model_dump(mode="json") for m in mats]


@mcp.tool()
async def gotit_upsert_drill_material(
    title: str,
    body: str,
    material_id: str | None = None,
) -> dict[str, object]:
    """Create or update a deep-dive material (pass id to update)."""
    await ensure_db()
    async with session_scope() as session:
        m = await day_ops.upsert_drill_material(
            session,
            material_id=UUID(material_id) if material_id else None,
            title=title,
            body=body,
            user_id=_user_id(),
        )
    return m.model_dump(mode="json")


@mcp.tool()
async def gotit_delete_drill_material(material_id: str) -> dict[str, str]:
    """Delete a deep-dive material by id."""
    await ensure_db()
    async with session_scope() as session:
        await day_ops.delete_drill_material(session, UUID(material_id), user_id=_user_id())
    return {"status": "deleted"}


@mcp.tool()
async def gotit_list_interviews(include_done: bool = False) -> list[dict[str, object]]:
    """List scheduled real-world interviews (newest scheduled first)."""
    await ensure_db()
    async with session_scope() as session:
        rows = await day_ops.list_interviews(
            session, user_id=_user_id(), include_done=include_done
        )
    return [r.model_dump(mode="json") for r in rows]


@mcp.tool()
async def gotit_upsert_interview(
    company: str,
    role_title: str,
    scheduled_at: str,
    interview_id: str | None = None,
    round: str | None = None,
    status: str = "scheduled",
    notes: str | None = None,
    remind_offsets_hours: list[int] | None = None,
) -> dict[str, object]:
    """Create or update a real-world interview. `scheduled_at` is ISO-8601 tz-aware."""
    await ensure_db()
    from datetime import datetime

    async with session_scope() as session:
        row = await day_ops.upsert_interview(
            session,
            interview_id=UUID(interview_id) if interview_id else None,
            company=company,
            role_title=role_title,
            scheduled_at=datetime.fromisoformat(scheduled_at.replace("Z", "+00:00")),
            round=round,
            status=InterviewStatus(status),
            notes=notes,
            remind_offsets_hours=remind_offsets_hours,
            user_id=_user_id(),
        )
    return row.model_dump(mode="json")


@mcp.tool()
async def gotit_update_interview_status(
    interview_id: str,
    status: str,
) -> dict[str, object]:
    """Update interview status: scheduled | done | cancelled."""
    await ensure_db()
    async with session_scope() as session:
        row = await day_ops.update_interview_status(
            session,
            UUID(interview_id),
            InterviewStatus(status),
            user_id=_user_id(),
        )
    return row.model_dump(mode="json")


@mcp.tool()
async def gotit_list_due_interview_reminders(
    now: str | None = None,
) -> list[dict[str, object]]:
    """Return due interview reminders for OpenClaw cron (offset + fire_at)."""
    await ensure_db()
    from datetime import UTC, datetime

    at = (
        datetime.fromisoformat(now.replace("Z", "+00:00"))
        if now
        else datetime.now(UTC)
    )
    async with session_scope() as session:
        due = await day_ops.list_due_interview_reminders(session, at, user_id=_user_id())
    return [d.model_dump(mode="json") for d in due]


@mcp.tool()
async def gotit_mark_interview_reminded(
    interview_id: str,
    at: str | None = None,
) -> dict[str, object]:
    """Mark an interview reminder as sent (updates last_reminded_at)."""
    await ensure_db()
    from datetime import datetime

    reminded_at = (
        datetime.fromisoformat(at.replace("Z", "+00:00")) if at else None
    )
    async with session_scope() as session:
        row = await day_ops.mark_interview_reminded(
            session,
            UUID(interview_id),
            at=reminded_at,
            user_id=_user_id(),
        )
    return row.model_dump(mode="json")


@mcp.tool()
async def gotit_list_drill_sessions() -> list[dict[str, object]]:
    """List all mock-interview drill sessions (newest first)."""
    await ensure_db()
    async with session_scope() as session:
        sessions = await day_ops.list_drill_sessions(session, user_id=_user_id())
    return [s.model_dump(mode="json") for s in sessions]


@mcp.tool()
async def gotit_get_drill_session(session_id: str) -> dict[str, object]:
    """Get a single drill session (with messages)."""
    await ensure_db()
    async with session_scope() as session:
        s = await day_ops.get_drill_session(session, UUID(session_id), user_id=_user_id())
    return s.model_dump(mode="json")


@mcp.tool()
async def gotit_start_drill_session(
    round: str,
    direction: str | None = None,
    project_id: str | None = None,
    thread_id: str | None = None,
) -> dict[str, object]:
    """Start a resume-driven mock interview session. `round` is tech_1/2/3/4/hr.
    Optional `thread_id` appends turns to the companion thread stream."""
    await ensure_db()
    settings = get_settings()
    user_id = _user_id()
    tid = UUID(thread_id) if thread_id else None
    async with session_scope() as session:
        resume = await day_ops.get_resume(session, user_id=user_id)
        if resume is None:
            raise ValueError("no resume imported yet; upload a resume first")
        round_ = DrillRound(round)
        project: Project | None = None
        if project_id:
            project = await day_ops.get_project(session, UUID(project_id), user_id=user_id)
        materials = await day_ops.list_drill_materials(session, user_id=user_id)
        ds = await day_ops.create_drill_session(
            session,
            resume_id=resume.id,
            round_=round_,
            direction=direction,
            project_id=UUID(project_id) if project_id else None,
            user_id=user_id,
        )
        verdict = await _mcp_run_sage(
            settings, session,
            user_id=user_id,
            resume=resume.document,
            materials=materials,
            project=project,
            round_=round_,
            direction=direction,
            answer=None,
        )
        await day_ops.append_drill_message(
            session, ds.id, role="examiner", text=verdict.follow_up or "", user_id=user_id
        )
        if verdict.done:
            await day_ops.finish_drill_session(session, ds.id, user_id=user_id)
        if tid is not None:
            await day_ops.append_workflow_exchange(
                session,
                thread_id=tid,
                user_id=user_id,
                workflow="drill",
                agent_name="sage",
                agent_text=drill_agent_text(
                    done=verdict.done,
                    depth_reached=verdict.depth_reached,
                    gaps=list(verdict.gaps),
                    follow_up=verdict.follow_up,
                ),
                user_text=None,
                extra_metadata={
                    "drill_session_id": str(ds.id),
                    "session_done": verdict.done,
                },
            )
    return {"session": ds.model_dump(mode="json"), "verdict": verdict.model_dump(mode="json")}


@mcp.tool()
async def gotit_continue_drill_session(
    session_id: str,
    answer: str,
    thread_id: str | None = None,
) -> dict[str, object]:
    """Continue a drill session with the candidate's latest answer.
    Optional `thread_id` appends turns to the companion thread stream."""
    await ensure_db()
    settings = get_settings()
    user_id = _user_id()
    tid = UUID(thread_id) if thread_id else None
    async with session_scope() as session:
        ds = await day_ops.get_drill_session(session, UUID(session_id), user_id=user_id)
        if ds.status == "done":
            raise ValueError("session already done")
        resume = await day_ops.get_resume(session, user_id=user_id)
        if resume is None:
            raise ValueError("no resume")
        project: Project | None = None
        if ds.project_id:
            try:
                project = await day_ops.get_project(session, ds.project_id, user_id=user_id)
            except KeyError:
                project = None
        materials = await day_ops.list_drill_materials(session, user_id=user_id)
        await day_ops.append_drill_message(
            session, ds.id, role="user", text=answer, user_id=user_id
        )
        verdict = await _mcp_run_sage(
            settings, session,
            user_id=user_id,
            resume=resume.document,
            materials=materials,
            project=project,
            round_=ds.round,
            direction=ds.direction,
            answer=answer,
        )
        await day_ops.append_drill_message(
            session, ds.id, role="examiner", text=verdict.follow_up or "", user_id=user_id
        )
        if verdict.done:
            await day_ops.finish_drill_session(session, ds.id, user_id=user_id)
        if tid is not None:
            await day_ops.append_workflow_exchange(
                session,
                thread_id=tid,
                user_id=user_id,
                workflow="drill",
                agent_name="sage",
                agent_text=drill_agent_text(
                    done=verdict.done,
                    depth_reached=verdict.depth_reached,
                    gaps=list(verdict.gaps),
                    follow_up=verdict.follow_up,
                ),
                user_text=answer,
                extra_metadata={
                    "drill_session_id": str(ds.id),
                    "session_done": verdict.done,
                },
            )
    return {"verdict": verdict.model_dump(mode="json")}


# --- helpers ---


def _resume_content_type(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    return {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "txt": "text/plain",
        "md": "text/markdown",
    }.get(ext, "text/plain")


def _resume_ext(content_type: str) -> str:
    return {
        "application/pdf": "pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "text/plain": "txt",
        "text/markdown": "md",
    }[content_type]


async def _mcp_active_prompt(agent_name: str) -> str:
    async with session_scope() as session:
        prompt = await SessionPromptReader(session).get_active_prompt(agent_name)
        return prompt.system_prompt if prompt else ""


async def _mcp_run_sage(
    settings: Settings,
    session: AsyncSession,
    *,
    user_id: str,
    resume: ResumeDocument,
    materials: list[DrillMaterial],
    project: Project | None,
    round_: DrillRound,
    direction: str | None,
    answer: str | None,
) -> SageVerdict:
    if not settings.llm_api_key:
        return stub_sage(round_=round_, project=project, answer=answer)
    system_prompt = await SessionPromptReader(session).get_active_prompt("sage")
    system_prompt_text = system_prompt.system_prompt if system_prompt else ""
    reader = SessionMemoryReader(session, user_id=user_id)
    agent = build_sage_agent(get_model(), system_prompt=system_prompt_text)
    return await run_sage(
        agent,
        reader,
        resume=resume,
        materials=materials,
        project=project,
        round_=round_,
        direction=direction,
        answer=answer,
    )


@mcp.tool()
async def gotit_create_thread(title: str, kind: str = "chat") -> dict[str, object]:
    """Create a learning conversation thread (kind: chat | verify)."""
    await ensure_db()
    async with session_scope() as session:
        thread = await day_ops.create_thread(
            session, user_id=_user_id(), title=title, kind=kind
        )
        return thread.model_dump(mode="json")


@mcp.tool()
async def gotit_list_threads(kind: str | None = None) -> list[dict[str, object]]:
    """List the learner's conversation threads."""
    await ensure_db()
    async with session_scope() as session:
        threads = await day_ops.list_threads(session, user_id=_user_id(), kind=kind)
        return [t.model_dump(mode="json") for t in threads]


@mcp.tool()
async def gotit_delete_thread(thread_id: str) -> dict[str, object]:
    """Delete a conversation thread and its messages."""
    await ensure_db()
    async with session_scope() as session:
        ok = await day_ops.delete_thread(
            session, UUID(thread_id), user_id=_user_id()
        )
        if not ok:
            return {"error": "thread not found"}
        return {"ok": True}


@mcp.tool()
async def gotit_list_messages(thread_id: str) -> list[dict[str, object]]:
    """Replay a thread's message history."""
    await ensure_db()
    async with session_scope() as session:
        msgs = await day_ops.list_messages(session, thread_id=UUID(thread_id))
        return [m.model_dump(mode="json") for m in msgs]


@mcp.tool()
async def gotit_post_message(
    thread_id: str,
    text: str,
    mentions: list[str] | None = None,
    skills: list[str] | None = None,
    handoff_to: str | None = None,
) -> dict[str, object]:
    """Post a learner message to a thread and get the agent reply chain.

    Routes by @mention (first mention wins), else current ball holder, else
    default agent. Agents may hand off to each other (A2A 接力); every reply in
    the chain is returned. Returns {user_message, agent_messages, thread?}.
    """
    await ensure_db()
    settings = get_settings()
    user_id = _user_id()
    async with session_scope() as session:
        tid = UUID(thread_id)
        thread = await day_ops.get_thread(session, tid)
        if thread is None or thread.user_id != user_id:
            return {"error": "thread not found"}
        from gotit.api.chat_orchestrator import post_message_chain

        reply = await post_message_chain(
            session,
            settings=settings,
            user_id=user_id,
            thread=thread,
            text=text,
            mentions=list(mentions or []),
            skills=list(skills or []),
            handoff_to=handoff_to,
        )
        out: dict[str, object] = {
            "user_message": reply.user_message.model_dump(mode="json"),
            "agent_messages": [m.model_dump(mode="json") for m in reply.agent_messages],
        }
        if reply.thread is not None:
            out["thread"] = reply.thread.model_dump(mode="json")
        return out


@mcp.tool()
async def gotit_seed_identities() -> list[dict[str, object]]:
    """Seed the 5 default agent identities (axiom/compass/echo/sage/critic)."""
    await ensure_db()
    async with session_scope() as session:
        seeded = await day_ops.seed_default_identities(session)
        return [i.model_dump(mode="json") for i in seeded]


@mcp.tool()
async def gotit_list_skills() -> list[dict[str, object]]:
    """List skill catalog (builtin + user installs) with enabled flags."""
    await ensure_db()
    async with session_scope() as session:
        items = await day_ops.list_skill_catalog(session, user_id=_user_id())
        return [s.model_dump(mode="json") for s in items]


@mcp.tool()
async def gotit_get_skill(name: str) -> dict[str, object]:
    """Get skill markdown for view/edit (editable=false for builtins)."""
    await ensure_db()
    try:
        async with session_scope() as session:
            detail = await day_ops.get_skill_detail(
                session, user_id=_user_id(), name=name
            )
            return detail.model_dump(mode="json")
    except KeyError as exc:
        return {"error": str(exc)}


@mcp.tool()
async def gotit_install_skill(markdown: str, name: str | None = None) -> dict[str, object]:
    """Install a skill from SKILL.md / markdown content (for companion agents)."""
    await ensure_db()
    try:
        async with session_scope() as session:
            skill = await day_ops.install_skill(
                session,
                user_id=_user_id(),
                raw_markdown=markdown,
                fallback_name=name,
            )
            return skill.model_dump(mode="json")
    except ValueError as exc:
        return {"error": str(exc)}


@mcp.tool()
async def gotit_update_skill(name: str, markdown: str) -> dict[str, object]:
    """Update markdown of a user-installed skill (name in frontmatter must match)."""
    await ensure_db()
    try:
        async with session_scope() as session:
            skill = await day_ops.update_skill_markdown(
                session,
                user_id=_user_id(),
                name=name,
                raw_markdown=markdown,
            )
            return skill.model_dump(mode="json")
    except (KeyError, ValueError) as exc:
        return {"error": str(exc)}


@mcp.tool()
async def gotit_set_skill_enabled(name: str, enabled: bool) -> dict[str, object]:
    """Enable or disable a skill in the catalog."""
    await ensure_db()
    try:
        async with session_scope() as session:
            skill = await day_ops.set_skill_enabled(
                session, user_id=_user_id(), name=name, enabled=enabled
            )
            return skill.model_dump(mode="json")
    except KeyError as exc:
        return {"error": str(exc)}


@mcp.tool()
async def gotit_delete_skill(name: str) -> dict[str, object]:
    """Delete a user-installed skill (or clear a builtin override)."""
    await ensure_db()
    try:
        async with session_scope() as session:
            await day_ops.delete_user_skill(session, user_id=_user_id(), name=name)
            return {"ok": True}
    except KeyError as exc:
        return {"error": str(exc)}


@mcp.tool()
async def gotit_list_connectors() -> list[dict[str, object]]:
    """List MCP connectors configured for companion agents."""
    await ensure_db()
    async with session_scope() as session:
        items = await day_ops.list_connectors(session, user_id=_user_id())
        return [c.model_dump(mode="json") for c in items]


@mcp.tool()
async def gotit_upsert_connector(
    name: str,
    transport: str,
    config: dict[str, object] | None = None,
    enabled: bool = True,
) -> dict[str, object]:
    """Create or replace an MCP connector (stdio | http | sse)."""
    await ensure_db()
    if transport not in ("stdio", "http", "sse"):
        return {"error": "transport must be stdio|http|sse"}
    try:
        async with session_scope() as session:
            conn = await day_ops.upsert_connector(
                session,
                user_id=_user_id(),
                name=name,
                transport=transport,  # type: ignore[arg-type]
                config=dict(config or {}),
                enabled=enabled,
            )
            return conn.model_dump(mode="json")
    except ValueError as exc:
        return {"error": str(exc)}


@mcp.tool()
async def gotit_import_connectors(
    config: dict[str, object],
) -> list[dict[str, object]] | dict[str, object]:
    """Import connectors from Claude/Cursor-style mcpServers JSON."""
    await ensure_db()
    try:
        async with session_scope() as session:
            items = await day_ops.import_connectors(
                session, user_id=_user_id(), payload=dict(config)
            )
            return [c.model_dump(mode="json") for c in items]
    except ValueError as exc:
        return {"error": str(exc)}


@mcp.tool()
async def gotit_delete_connector(connector_id: str) -> dict[str, object]:
    """Delete an MCP connector by id."""
    await ensure_db()
    try:
        async with session_scope() as session:
            await day_ops.delete_connector(
                session, user_id=_user_id(), connector_id=UUID(connector_id)
            )
            return {"ok": True}
    except (KeyError, ValueError) as exc:
        return {"error": str(exc)}


@mcp.tool()
async def gotit_start_verify(
    thread_id: str, claim_id: str, answer: str | None = None, examine_verdict: str | None = None
) -> dict[str, object]:
    """Run the verify-loop (examine → recheck → gate) for one claim in a thread.

    The gate is deterministic code (no LLM): stricter of examiner's and critic's
    verdicts. Recheck is done by Critic, a different agent from Axiom.
    """
    await ensure_db()
    settings = get_settings()
    user_id = _user_id()
    from gotit.core.agents.axiom import build_axiom_agent, run_axiom
    from gotit.core.agents.critic import build_critic_agent, run_critic, stub_critic
    from gotit.core.loop import VerifyWorkflow

    async with session_scope() as session:
        tid = UUID(thread_id)
        cid = UUID(claim_id)
        claim = await session.get(ClaimRow, cid)
        if claim is None or claim.user_id != user_id:
            return {"error": "claim not found"}

        from gotit.db.ops.graph import build_budget_subgraph, record_verify_mastery_writeback
        from gotit.db.ops.memory import (
            append_trajectory,
            build_failure_lesson_block,
            count_prior_failures,
            list_trajectory,
        )

        trajectory = await list_trajectory(
            session, user_id=user_id, topic=claim.topic, claim_id=cid
        )
        prior_failures = count_prior_failures(trajectory, claim_id=cid)
        budget = await build_budget_subgraph(session, user_id=user_id, claim_id=cid)
        lesson_block = await build_failure_lesson_block(
            session,
            user_id=user_id,
            claim_id=cid,
            topic=claim.topic,
            neighbor_claim_ids=budget.confused_claim_ids,
        )

        if examine_verdict is not None:
            ex_verdict = examine_verdict
            ex_score: float | None = None
            ex_evidence: str | None = None
        elif not settings.llm_api_key:
            ex_verdict = "passed"
            ex_score = None
            ex_evidence = None
        else:
            prompt = await SessionPromptReader(session).get_active_prompt("axiom")
            system_prompt = prompt.system_prompt if prompt else ""
            reader = SessionMemoryReader(session, user_id=user_id)
            agent = build_axiom_agent(get_model(), system_prompt=system_prompt)
            ev = await run_axiom(
                agent, reader, claim_text=claim.text,
                answer=answer, trajectory=trajectory,
                budget_block=budget.prompt_block,
                failure_lesson_block=lesson_block,
            )
            ex_verdict = ev.verdict or "almost"
            ex_score = ev.score
            ex_evidence = ev.evidence

        ball = VerifyWorkflow.start(tid, cid)
        ball = VerifyWorkflow.on_examine(
            ball, verdict=ex_verdict, score=ex_score, evidence=ex_evidence
        )
        await day_ops.set_ball(
            session, thread_id=tid, holder=ball.holder, stage=ball.stage, context=ball.context
        )

        critic_identity = await day_ops.get_identity(session, "critic")
        critic_cfg = critic_identity.llm_config if critic_identity else None
        critic_binding = resolve_critic_binding(critic_cfg, settings=settings)
        if not critic_binding.api_key:
            recheck = stub_critic(examine_verdict=ex_verdict)
        else:
            cprompt = await SessionPromptReader(session).get_active_prompt("critic")
            csystem = cprompt.system_prompt if cprompt else ""
            creader = SessionMemoryReader(session, user_id=user_id)
            cagent = build_critic_agent(
                get_critic_model(critic_cfg, settings=settings),
                system_prompt=csystem,
            )
            recheck = await run_critic(
                cagent, creader,
                claim_text=claim.text,
                examine_verdict=ex_verdict,
                examine_score=ex_score,
                examine_evidence=ex_evidence,
                learner_answer=answer,
            )

        ball = VerifyWorkflow.on_recheck(ball, verdict=recheck.verdict)
        await day_ops.set_ball(
            session, thread_id=tid, holder=ball.holder, stage=ball.stage, context=ball.context
        )
        gate = VerifyWorkflow.gate(ball, prior_failures=prior_failures)
        writeback = await day_ops.apply_examine_verdict(
            session, cid, verdict=gate.verdict, user_id=user_id,
            prior_failures=prior_failures,
        )
        await day_ops.clear_ball(session, tid)
        await append_trajectory(
            session, user_id=user_id, claim_id=cid, topic=claim.topic,
            verdict=ex_verdict, gate_verdict=gate.verdict,
            score=ex_score, reason=gate.reason,
        )
        mastery = await record_verify_mastery_writeback(
            session,
            user_id=user_id,
            claim_id=cid,
            topic=claim.topic,
            gate_verdict=gate.verdict,
            score=ex_score,
            reason=gate.reason,
        )
        await day_ops.add_message(
            session, thread_id=tid, role="agent", agent_name="gate",
            text=f"验证完成：{gate.reason}",
            metadata={"claim_id": str(cid), "gate_verdict": gate.verdict},
        )
        return {
            "examine_verdict": ex_verdict,
            "recheck_verdict": recheck.verdict,
            "gate": gate.model_dump(mode="json"),
            "writeback": writeback,
            "mastery_graph": mastery,
        }


@mcp.tool()
async def gotit_calibration_start(
    note_id: str | None = None,
    topic: str | None = None,
    claim_ids: list[str] | None = None,
) -> dict[str, object]:
    """Start a cold-start calibration session (CAT-lite; no Critic)."""
    await ensure_db()
    ids = [UUID(c) for c in claim_ids] if claim_ids else None
    nid = UUID(note_id) if note_id else None
    async with session_scope() as session:
        view = await day_ops.start_calibration(
            session,
            user_id=_user_id(),
            note_id=nid,
            topic=topic,
            claim_ids=ids,
        )
        return view.model_dump(mode="json")


@mcp.tool()
async def gotit_calibration_answer(
    session_id: str,
    claim_id: str,
    outcome: str,
) -> dict[str, object]:
    """Answer one calibration item: outcome=correct|incorrect."""
    if outcome not in {"correct", "incorrect"}:
        raise ValueError("outcome must be correct or incorrect")
    await ensure_db()
    async with session_scope() as session:
        view = await day_ops.answer_calibration(
            session,
            UUID(session_id),
            claim_id=UUID(claim_id),
            outcome=outcome,  # type: ignore[arg-type]
            user_id=_user_id(),
        )
        return view.model_dump(mode="json")


@mcp.tool()
async def gotit_calibration_get(session_id: str) -> dict[str, object]:
    """Get calibration session + trace."""
    await ensure_db()
    async with session_scope() as session:
        view = await day_ops.get_calibration(
            session, UUID(session_id), user_id=_user_id()
        )
        return view.model_dump(mode="json")


@mcp.tool()
async def gotit_calibration_synthetic(
    true_theta: float,
    note_id: str | None = None,
    topic: str | None = None,
    claim_ids: list[str] | None = None,
    mode: str = "deterministic",
) -> dict[str, object]:
    """Replay calibration for a known ability; returns theta_hat and abs_error."""
    if mode not in {"deterministic", "bernoulli_threshold"}:
        raise ValueError("mode must be deterministic or bernoulli_threshold")
    await ensure_db()
    ids = [UUID(c) for c in claim_ids] if claim_ids else None
    nid = UUID(note_id) if note_id else None
    async with session_scope() as session:
        result = await day_ops.run_synthetic_calibration(
            session,
            true_theta=true_theta,
            note_id=nid,
            topic=topic,
            claim_ids=ids,
            user_id=_user_id(),
            mode=mode,  # type: ignore[arg-type]
        )
        return result.model_dump(mode="json")


def main() -> None:
    # stdio transport for local OpenClaw / MCP hosts
    anyio.run(mcp.run_stdio_async)


if __name__ == "__main__":
    main()
