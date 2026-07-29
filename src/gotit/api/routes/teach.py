"""Teach-back (Echo) endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from gotit.api.auth import require_api_key
from gotit.api.deps import SessionMemoryReader, SessionPromptReader, get_model
from gotit.api.routes._common import _user_id
from gotit.api.settings import Settings, get_settings
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


@router.post("/v1/teach", dependencies=[Depends(require_api_key)])
async def teach(
    body: TeachRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    user_id = _user_id(settings)

    if body.you_taught_well is not None:
        return {
            "verdict": TeachVerdict(
                done=True,
                you_taught_well=body.you_taught_well,
                gaps=[],
                next_question=None,
            ).model_dump(mode="json")
        }

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
    return {"verdict": verdict.model_dump(mode="json")}
