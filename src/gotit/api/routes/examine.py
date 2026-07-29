"""Examine (Axiom) — single-claim, note-session, and topic-session modes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from gotit.api.auth import require_api_key
from gotit.api.deps import SessionMemoryReader, SessionPromptReader, get_model
from gotit.api.routes._common import _user_id
from gotit.api.settings import Settings, get_settings
from gotit.core.agents.axiom import (
    build_axiom_agent,
    build_topic_axiom_agent,
    run_axiom,
    run_topic_examine,
    stub_topic_examine,
)
from gotit.db import ops as day_ops
from gotit.db import session_scope
from gotit.db.models import ClaimRow

router = APIRouter()


class ExamineRequest(BaseModel):
    claim_id: UUID | None = Field(
        default=None,
        description="Single-claim mode target; used when topic/note_id absent.",
    )
    topic: str | None = Field(
        default=None,
        description="Topic-session mode: Axiom shuttles across the topic's claims.",
    )
    note_id: UUID | None = Field(
        default=None,
        description="Note-session mode: Axiom shuttles across the note's claims.",
    )
    answer: str | None = Field(
        default=None,
        description="Learner's latest answer; omit on the first turn.",
    )
    history: list[dict[str, str]] = Field(
        default_factory=list,
        description="Prior turns [{role: examiner|user, text}].",
    )
    verdict: str | None = Field(
        default=None,
        description=(
            "Direct verdict (passed|almost|owe_next) bypassing the agent; "
            "used for stubs/tests (single-claim mode only)."
        ),
    )


@router.post("/v1/examine", dependencies=[Depends(require_api_key)])
async def examine(
    body: ExamineRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    user_id = _user_id(settings)

    # --- Claims-session modes (note_id or topic): Axiom shuttles across claims ---
    if body.note_id is not None or body.topic is not None:
        async with session_scope() as session:
            if body.note_id is not None:
                claims = await day_ops.list_note_claims(
                    session, body.note_id, user_id=user_id
                )
            elif body.topic is not None:
                claims = await day_ops.list_topic_claims_today(
                    session, body.topic, user_id=user_id
                )
        if not settings.llm_api_key:
            session_verdict = stub_topic_examine(
                claims=claims, answer=body.answer, history=body.history
            )
        else:
            async with session_scope() as session:
                prompt = await SessionPromptReader(session).get_active_prompt("axiom")
                system_prompt = prompt.system_prompt if prompt else ""
                reader = SessionMemoryReader(session, user_id=user_id)
                claims_agent = build_topic_axiom_agent(
                    get_model(), system_prompt=system_prompt
                )
            session_verdict = await run_topic_examine(
                claims_agent,
                reader,
                topic=body.topic or "",
                claims=claims,
                history=body.history,
                answer=body.answer,
            )
        writeback: dict[str, object] | None = None
        if (
            session_verdict.done
            and session_verdict.verdict is not None
            and session_verdict.current_claim_id
        ):
            try:
                async with session_scope() as session:
                    writeback = await day_ops.apply_examine_verdict(
                        session,
                        session_verdict.current_claim_id,
                        verdict=session_verdict.verdict,
                        user_id=user_id,
                    )
            except KeyError as exc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
                ) from exc
        return {
            "verdict": session_verdict.model_dump(mode="json"),
            "writeback": writeback,
        }

    # --- Single-claim mode (legacy) ---
    if body.claim_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="one of `note_id`, `topic`, or `claim_id` is required",
        )

    # Direct-verdict path: bypass the agent (stub / tests / manual override).
    if body.verdict is not None:
        try:
            async with session_scope() as session:
                direct_writeback = await day_ops.apply_examine_verdict(
                    session,
                    body.claim_id,
                    verdict=body.verdict,
                    user_id=user_id,
                )
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        return {
            "verdict": {
                "done": True,
                "verdict": body.verdict,
                "score": None,
                "evidence": None,
                "follow_up": "",
            },
            "writeback": direct_writeback,
        }

    # Agent path: multi-turn examination.
    try:
        async with session_scope() as session:
            claim = await session.get(ClaimRow, body.claim_id)
            if claim is None or claim.user_id != user_id:
                raise KeyError(f"claim not found: {body.claim_id}")
            prompt = await SessionPromptReader(session).get_active_prompt("axiom")
            system_prompt = prompt.system_prompt if prompt else ""
            reader = SessionMemoryReader(session, user_id=user_id)
            agent = build_axiom_agent(get_model(), system_prompt=system_prompt)
            verdict = await run_axiom(
                agent,
                reader,
                claim_text=claim.text,
                history=body.history,
                answer=body.answer,
            )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    writeback = None
    if verdict.done and verdict.verdict is not None:
        try:
            async with session_scope() as session:
                writeback = await day_ops.apply_examine_verdict(
                    session,
                    body.claim_id,
                    verdict=verdict.verdict,
                    user_id=user_id,
                )
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return {"verdict": verdict.model_dump(mode="json"), "writeback": writeback}
