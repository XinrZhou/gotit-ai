from __future__ import annotations

from uuid import UUID

from gotit.api.settings import get_settings
from gotit.db import ops as day_ops
from gotit.db import session_scope
from gotit.db.runtime import ensure_db
from gotit.mcp.app import mcp
from gotit.mcp.common import (
    _user_id,
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

