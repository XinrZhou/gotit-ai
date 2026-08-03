"""Chat surface — threads, messages, agent replies.

The companion's primary surface: a learner talks in a thread, @mentions route to
a specific agent (default axiom), and the addressed agent replies in-character
using its persistent identity (personality + pinned rubric) plus thread history
and long-term memory. Verify-loop trigger (`POST /v1/threads/{id}/verify`) is
wired in P2.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from gotit.api.auth import require_api_key
from gotit.api.chat_orchestrator import post_message_chain
from gotit.api.routes._common import _user_id
from gotit.api.settings import Settings, get_settings
from gotit.core.models import AgentReply, Message, Thread
from gotit.db import ops as day_ops
from gotit.db import session_scope
from gotit.db.models import ClaimRow

router = APIRouter()


class ThreadCreate(BaseModel):
    title: str = Field(default="新对话", min_length=1, max_length=500)
    kind: str = Field(default="chat", pattern="^(chat|verify)$")


class MessagePost(BaseModel):
    text: str = Field(min_length=1)
    mentions: list[str] = Field(default_factory=list)
    skills: list[str] = Field(
        default_factory=list,
        description="On-demand skill names to inject into the agent's prompt this turn.",
    )
    handoff_to: str | None = Field(
        default=None,
        description="Manual A2A handoff: force the first holder to cede the floor "
        "to this agent (bypass / tests). Empty = let the agent decide.",
    )


@router.post(
    "/v1/threads",
    response_model=Thread,
    dependencies=[Depends(require_api_key)],
)
async def create_thread(
    body: ThreadCreate,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Thread:
    async with session_scope() as session:
        return await day_ops.create_thread(
            session,
            user_id=_user_id(settings),
            title=body.title,
            kind=body.kind,
        )


@router.get(
    "/v1/threads",
    response_model=list[Thread],
    dependencies=[Depends(require_api_key)],
)
async def list_threads(
    settings: Annotated[Settings, Depends(get_settings)],
    kind: Annotated[str | None, Query()] = None,
) -> list[Thread]:
    async with session_scope() as session:
        return await day_ops.list_threads(
            session, user_id=_user_id(settings), kind=kind
        )


class ThreadPatch(BaseModel):
    title: str = Field(min_length=1, max_length=500)


@router.patch(
    "/v1/threads/{thread_id}",
    response_model=Thread,
    dependencies=[Depends(require_api_key)],
)
async def patch_thread(
    thread_id: UUID,
    body: ThreadPatch,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Thread:
    async with session_scope() as session:
        thread = await day_ops.get_thread(session, thread_id)
        if thread is None or thread.user_id != _user_id(settings):
            raise HTTPException(status_code=404, detail="thread not found")
        updated = await day_ops.update_thread_title(
            session, thread_id, title=body.title.strip()
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="thread not found")
        return updated


@router.delete(
    "/v1/threads/{thread_id}",
    dependencies=[Depends(require_api_key)],
)
async def delete_thread(
    thread_id: UUID,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, bool]:
    async with session_scope() as session:
        ok = await day_ops.delete_thread(
            session, thread_id, user_id=_user_id(settings)
        )
        if not ok:
            raise HTTPException(status_code=404, detail="thread not found")
        return {"ok": True}


@router.get(
    "/v1/threads/{thread_id}/messages",
    response_model=list[Message],
    dependencies=[Depends(require_api_key)],
)
async def list_messages(
    thread_id: UUID,
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[Message]:
    async with session_scope() as session:
        thread = await day_ops.get_thread(session, thread_id)
        if thread is None or thread.user_id != _user_id(settings):
            raise HTTPException(status_code=404, detail="thread not found")
        return await day_ops.list_messages(session, thread_id=thread_id)


@router.post(
    "/v1/threads/{thread_id}/messages",
    response_model=AgentReply,
    dependencies=[Depends(require_api_key)],
)
async def post_message(
    thread_id: UUID,
    body: MessagePost,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AgentReply:
    user_id = _user_id(settings)
    async with session_scope() as session:
        thread = await day_ops.get_thread(session, thread_id)
        if thread is None or thread.user_id != user_id:
            raise HTTPException(status_code=404, detail="thread not found")
        try:
            return await post_message_chain(
                session,
                settings=settings,
                user_id=user_id,
                thread=thread,
                text=body.text,
                mentions=list(body.mentions),
                skills=list(body.skills),
                handoff_to=body.handoff_to,
            )
        except KeyError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception as exc:
            # Surface a short, actionable reason (LLM/gateway structured-output issues).
            detail = str(exc).split("\n", 1)[0][:240]
            raise HTTPException(
                status_code=502,
                detail=f"搭子暂时没回上（{type(exc).__name__}: {detail}）",
            ) from exc


class VerifyRequest(BaseModel):
    claim_id: UUID
    answer: str | None = None
    examine_verdict: str | None = Field(
        default=None,
        description="Direct examine verdict bypass (passed|almost|owe_next); "
        "used for stubs/tests or when the examine already happened.",
    )


@router.post(
    "/v1/threads/{thread_id}/verify",
    dependencies=[Depends(require_api_key)],
)
async def start_verify(
    thread_id: UUID,
    body: VerifyRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    """Run the verify-loop (examine → recheck → gate) for one claim in a thread.

    The gate is deterministic code (no LLM): it takes the stricter of the
    examiner's and the critic's verdicts. Recheck is done by Critic, a different
    agent from Axiom — no agent reviews its own judgment.
    """
    from gotit.api.verify_attempt import run_verify_attempt

    user_id = _user_id(settings)
    async with session_scope() as session:
        thread = await day_ops.get_thread(session, thread_id)
        if thread is None or thread.user_id != user_id:
            raise HTTPException(status_code=404, detail="thread not found")
        claim = await session.get(ClaimRow, body.claim_id)
        if claim is None or claim.user_id != user_id:
            raise HTTPException(status_code=404, detail="claim not found")

        try:
            return await run_verify_attempt(
                session,
                thread_id=thread_id,
                claim=claim,
                user_id=user_id,
                settings=settings,
                answer=body.answer,
                examine_verdict=body.examine_verdict,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
