from __future__ import annotations

from datetime import date
from uuid import UUID

from gotit.api.deps import (
    SessionMemoryReader,
    SessionPromptReader,
    get_model,
)
from gotit.api.settings import get_settings
from gotit.core.agents.compass import build_compass_agent, run_compass
from gotit.core.models import (
    MasteryStatus,
)
from gotit.db import ops as day_ops
from gotit.db import session_scope
from gotit.db.models import DayNoteRow
from gotit.db.runtime import ensure_db
from gotit.mcp.app import mcp
from gotit.mcp.common import (
    _user_id,
)


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

