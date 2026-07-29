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
from gotit.api.deps import (
    SessionMemoryReader,
    SessionPromptReader,
    get_model,
)
from gotit.api.routes._common import _user_id
from gotit.api.settings import Settings, get_settings
from gotit.core.agents.axiom import build_axiom_agent, run_axiom
from gotit.core.agents.critic import build_critic_agent, run_critic, stub_critic
from gotit.core.loop import VerifyWorkflow
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
    user_id = _user_id(settings)
    async with session_scope() as session:
        thread = await day_ops.get_thread(session, thread_id)
        if thread is None or thread.user_id != user_id:
            raise HTTPException(status_code=404, detail="thread not found")
        claim = await session.get(ClaimRow, body.claim_id)
        if claim is None or claim.user_id != user_id:
            raise HTTPException(status_code=404, detail="claim not found")

        # --- examine (axiom) ---
        from gotit.db.ops.memory import count_prior_failures, list_trajectory

        trajectory = await list_trajectory(
            session, user_id=user_id, topic=claim.topic, claim_id=body.claim_id
        )
        prior_failures = count_prior_failures(trajectory, claim_id=body.claim_id)

        if body.examine_verdict is not None:
            examine_verdict = body.examine_verdict
            examine_score: float | None = None
            examine_evidence: str | None = None
        elif not settings.llm_api_key:
            examine_verdict = "passed"
            examine_score = None
            examine_evidence = None
        else:
            prompt = await SessionPromptReader(session).get_active_prompt("axiom")
            system_prompt = prompt.system_prompt if prompt else ""
            reader = SessionMemoryReader(session, user_id=user_id)
            agent = build_axiom_agent(get_model(), system_prompt=system_prompt)
            ev = await run_axiom(
                agent,
                reader,
                claim_text=claim.text,
                answer=body.answer,
                trajectory=trajectory,
            )
            examine_verdict = ev.verdict or "almost"
            examine_score = ev.score
            examine_evidence = ev.evidence

        ball = VerifyWorkflow.start(thread_id, body.claim_id)
        ball = VerifyWorkflow.on_examine(
            ball, verdict=examine_verdict, score=examine_score, evidence=examine_evidence
        )
        await day_ops.set_ball(
            session,
            thread_id=thread_id,
            holder=ball.holder,
            stage=ball.stage,
            context=ball.context,
        )

        # --- recheck (critic) ---
        if not settings.llm_api_key:
            recheck = stub_critic(examine_verdict=examine_verdict)
        else:
            cprompt = await SessionPromptReader(session).get_active_prompt("critic")
            csystem = cprompt.system_prompt if cprompt else ""
            creader = SessionMemoryReader(session, user_id=user_id)
            cagent = build_critic_agent(get_model(), system_prompt=csystem)
            recheck = await run_critic(
                cagent,
                creader,
                claim_text=claim.text,
                examine_verdict=examine_verdict,
                examine_score=examine_score,
                examine_evidence=examine_evidence,
                learner_answer=body.answer,
            )

        ball = VerifyWorkflow.on_recheck(ball, verdict=recheck.verdict)
        await day_ops.set_ball(
            session,
            thread_id=thread_id,
            holder=ball.holder,
            stage=ball.stage,
            context=ball.context,
        )

        # --- gate (deterministic, no LLM) ---
        gate = VerifyWorkflow.gate(ball)
        try:
            writeback = await day_ops.apply_examine_verdict(
                session,
                body.claim_id,
                verdict=gate.verdict,
                user_id=user_id,
                prior_failures=prior_failures,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        await day_ops.clear_ball(session, thread_id)

        # record this outcome as a trajectory entry for the learning curve
        from gotit.db.ops.memory import append_trajectory

        await append_trajectory(
            session,
            user_id=user_id,
            claim_id=body.claim_id,
            topic=claim.topic,
            verdict=examine_verdict,
            gate_verdict=gate.verdict,
            score=examine_score,
            reason=gate.reason,
        )

        # record the verdict in the thread as an agent message
        await day_ops.add_message(
            session,
            thread_id=thread_id,
            role="agent",
            agent_name="gate",
            text=f"验证完成：{gate.reason}",
            metadata={
                "claim_id": str(body.claim_id),
                "examine_verdict": examine_verdict,
                "recheck_verdict": recheck.verdict,
                "gate_verdict": gate.verdict,
            },
        )
        return {
            "examine_verdict": examine_verdict,
            "recheck_verdict": recheck.verdict,
            "gate": gate.model_dump(mode="json"),
            "writeback": writeback,
        }
