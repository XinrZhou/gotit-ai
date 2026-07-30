"""Teach-back (Echo) endpoint."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from gotit.api.auth import require_api_key
from gotit.api.deps import SessionMemoryReader, SessionPromptReader, get_model
from gotit.api.routes._common import _user_id
from gotit.api.settings import Settings, get_settings
from gotit.api.workflow_persist import persist_workflow_exchange, teach_agent_text
from gotit.core.agents.echo import build_echo_agent, run_echo
from gotit.core.models import TeachVerdict
from gotit.db import session_scope

router = APIRouter()


class TeachRequest(BaseModel):
    topic: str = Field(min_length=1)
    answer: str | None = Field(
        default=None,
        description="Learner's latest teaching turn; omit on the first turn.",
    )
    history: list[dict[str, str]] = Field(default_factory=list)
    you_taught_well: bool | None = Field(
        default=None,
        description="Direct verdict bypassing the agent (stub/tests).",
    )
    thread_id: UUID | None = Field(
        default=None,
        description="When set, append this turn into the companion thread stream.",
    )


async def _persist_teach(
    *,
    thread_id: UUID | None,
    user_id: str,
    topic: str,
    answer: str | None,
    verdict: TeachVerdict,
) -> None:
    if thread_id is None:
        return
    extra: dict[str, object] = {"topic": topic, "session_done": verdict.done}
    if verdict.you_taught_well is not None:
        extra["verdict"] = "passed" if verdict.you_taught_well else "owe_next"
    try:
        await persist_workflow_exchange(
            thread_id=thread_id,
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.post("/v1/teach", dependencies=[Depends(require_api_key)])
async def teach(
    body: TeachRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    user_id = _user_id(settings)

    if body.you_taught_well is not None:
        verdict = TeachVerdict(
            done=True,
            you_taught_well=body.you_taught_well,
            gaps=[],
            next_question=None,
        )
        await _persist_teach(
            thread_id=body.thread_id,
            user_id=user_id,
            topic=body.topic,
            answer=body.answer,
            verdict=verdict,
        )
        return {"verdict": verdict.model_dump(mode="json")}

    async with session_scope() as session:
        prompt = await SessionPromptReader(session).get_active_prompt("echo")
        system_prompt = prompt.system_prompt if prompt else ""
        reader = SessionMemoryReader(session, user_id=user_id)
        agent = build_echo_agent(get_model(), system_prompt=system_prompt)
        verdict = await run_echo(
            agent,
            reader,
            topic=body.topic,
            history=body.history,
            answer=body.answer,
        )
    await _persist_teach(
        thread_id=body.thread_id,
        user_id=user_id,
        topic=body.topic,
        answer=body.answer,
        verdict=verdict,
    )
    return {"verdict": verdict.model_dump(mode="json")}
