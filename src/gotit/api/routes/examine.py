"""Examine (Axiom) — single-claim, note-session, and topic-session modes."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from gotit.api.auth import require_api_key
from gotit.api.deps import SessionMemoryReader, SessionPromptReader, get_model
from gotit.api.routes._common import _user_id
from gotit.api.settings import Settings, get_settings
from gotit.api.verify_finalize import finalize_examine_with_gate
from gotit.api.workflow_persist import examine_agent_text, persist_workflow_exchange
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
            "Direct examine verdict (passed|almost|owe_next) bypassing Axiom; "
            "still runs Critic + deterministic gate (stubs/tests)."
        ),
    )
    thread_id: UUID | None = Field(
        default=None,
        description="When set, append this turn into the companion thread stream.",
    )


def _verify_meta(finalized: dict[str, Any]) -> dict[str, object]:
    return {
        "examine_verdict": finalized["examine_verdict"],
        "recheck_verdict": finalized["recheck_verdict"],
        "gate_verdict": finalized["gate_verdict"],
        "verdict": finalized["gate_verdict"],
        "gate": finalized["gate"],
    }


async def _persist_examine(
    *,
    thread_id: UUID | None,
    user_id: str,
    answer: str | None,
    agent_text: str,
    extra: dict[str, object],
) -> None:
    if thread_id is None:
        return
    try:
        await persist_workflow_exchange(
            thread_id=thread_id,
            user_id=user_id,
            workflow="examine",
            agent_text=agent_text,
            user_text=answer,
            extra_metadata=extra,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


async def _finalize_claim(
    *,
    claim_id: UUID,
    examine_verdict: str,
    user_id: str,
    settings: Settings,
    answer: str | None,
    thread_id: UUID | None,
    examine_score: float | None = None,
    examine_evidence: str | None = None,
) -> dict[str, Any]:
    async with session_scope() as session:
        claim = await session.get(ClaimRow, claim_id)
        if claim is None or claim.user_id != user_id:
            raise KeyError(f"claim not found: {claim_id}")
        return await finalize_examine_with_gate(
            session,
            claim_id=claim_id,
            claim_text=claim.text,
            topic=claim.topic,
            examine_verdict=examine_verdict,
            examine_score=examine_score,
            examine_evidence=examine_evidence,
            learner_answer=answer,
            user_id=user_id,
            settings=settings,
            thread_id=thread_id,
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
                from gotit.db.ops.memory import build_failure_lesson_block

                lesson_block: str | None = None
                if claims:
                    focus = claims[0]
                    lesson_block = await build_failure_lesson_block(
                        session,
                        user_id=user_id,
                        claim_id=focus.id,
                        topic=body.topic or focus.topic,
                        neighbor_claim_ids=[c.id for c in claims[1:]],
                    )
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
                failure_lesson_block=lesson_block,
            )
        writeback: dict[str, object] | None = None
        verify: dict[str, object] | None = None
        gate_verdict = session_verdict.verdict
        if (
            session_verdict.done
            and session_verdict.verdict is not None
            and session_verdict.current_claim_id
        ):
            try:
                finalized = await _finalize_claim(
                    claim_id=session_verdict.current_claim_id,
                    examine_verdict=session_verdict.verdict,
                    user_id=user_id,
                    settings=settings,
                    answer=body.answer,
                    thread_id=body.thread_id,
                )
            except KeyError as exc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
                ) from exc
            writeback = finalized["writeback"]
            verify = _verify_meta(finalized)
            gate_verdict = finalized["gate_verdict"]
        extra: dict[str, object] = {
            "session_done": session_verdict.session_done,
        }
        if body.note_id is not None:
            extra["note_id"] = str(body.note_id)
        if body.topic is not None:
            extra["topic"] = body.topic
        if session_verdict.current_claim_id:
            extra["claim_id"] = str(session_verdict.current_claim_id)
        if gate_verdict:
            extra["verdict"] = gate_verdict
        if verify:
            extra.update(verify)
        await _persist_examine(
            thread_id=body.thread_id,
            user_id=user_id,
            answer=body.answer,
            agent_text=examine_agent_text(
                follow_up=session_verdict.follow_up,
                done=session_verdict.done,
                verdict=gate_verdict,
            ),
            extra=extra,
        )
        verdict_payload = session_verdict.model_dump(mode="json")
        if gate_verdict is not None and session_verdict.done:
            verdict_payload["verdict"] = gate_verdict
        out: dict[str, object] = {
            "verdict": verdict_payload,
            "writeback": writeback,
        }
        if verify:
            out["verify"] = verify
        return out

    # --- Single-claim mode ---
    if body.claim_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="one of `note_id`, `topic`, or `claim_id` is required",
        )

    # Direct examine verdict: still Critic + gate (stub critic echoes when no key).
    if body.verdict is not None:
        try:
            finalized = await _finalize_claim(
                claim_id=body.claim_id,
                examine_verdict=body.verdict,
                user_id=user_id,
                settings=settings,
                answer=body.answer,
                thread_id=body.thread_id,
            )
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc
        verify = _verify_meta(finalized)
        await _persist_examine(
            thread_id=body.thread_id,
            user_id=user_id,
            answer=body.answer,
            agent_text=examine_agent_text(
                follow_up="",
                done=True,
                verdict=finalized["gate_verdict"],
            ),
            extra={
                "claim_id": str(body.claim_id),
                "session_done": True,
                **verify,
            },
        )
        return {
            "verdict": {
                "done": True,
                "verdict": finalized["gate_verdict"],
                "score": None,
                "evidence": None,
                "follow_up": "",
            },
            "writeback": finalized["writeback"],
            "verify": verify,
        }

    # Agent path: multi-turn examination.
    try:
        async with session_scope() as session:
            claim = await session.get(ClaimRow, body.claim_id)
            if claim is None or claim.user_id != user_id:
                raise KeyError(f"claim not found: {body.claim_id}")
            from gotit.db.ops.memory import build_failure_lesson_block

            lesson_block = await build_failure_lesson_block(
                session,
                user_id=user_id,
                claim_id=body.claim_id,
                topic=claim.topic,
            )
            prompt = await SessionPromptReader(session).get_active_prompt("axiom")
            system_prompt = prompt.system_prompt if prompt else ""
            reader = SessionMemoryReader(session, user_id=user_id)
            agent = build_axiom_agent(get_model(), system_prompt=system_prompt)
            claim_text = claim.text
            verdict = await run_axiom(
                agent,
                reader,
                claim_text=claim_text,
                history=body.history,
                answer=body.answer,
                failure_lesson_block=lesson_block,
            )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    writeback = None
    verify = None
    gate_verdict = verdict.verdict
    if verdict.done and verdict.verdict is not None:
        try:
            finalized = await _finalize_claim(
                claim_id=body.claim_id,
                examine_verdict=verdict.verdict,
                examine_score=verdict.score,
                examine_evidence=verdict.evidence,
                user_id=user_id,
                settings=settings,
                answer=body.answer,
                thread_id=body.thread_id,
            )
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        writeback = finalized["writeback"]
        verify = _verify_meta(finalized)
        gate_verdict = finalized["gate_verdict"]

    extra_single: dict[str, object] = {
        "claim_id": str(body.claim_id),
        "session_done": bool(verdict.done),
    }
    if gate_verdict:
        extra_single["verdict"] = gate_verdict
    if verify:
        extra_single.update(verify)
    await _persist_examine(
        thread_id=body.thread_id,
        user_id=user_id,
        answer=body.answer,
        agent_text=examine_agent_text(
            follow_up=verdict.follow_up,
            done=verdict.done,
            verdict=gate_verdict,
        ),
        extra=extra_single,
    )
    verdict_out = verdict.model_dump(mode="json")
    if gate_verdict is not None and verdict.done:
        verdict_out["verdict"] = gate_verdict
    result: dict[str, object] = {"verdict": verdict_out, "writeback": writeback}
    if verify:
        result["verify"] = verify
    return result
