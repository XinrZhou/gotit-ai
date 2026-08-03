"""Teach-back (Echo) endpoint — voice/text → shared verify finalize when claim-bound."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from gotit.api.action_blocks import attach_verdict_blocks
from gotit.api.auth import require_api_key
from gotit.api.deps import SessionMemoryReader, SessionPromptReader, get_model
from gotit.api.routes._common import _user_id
from gotit.api.settings import Settings, get_settings
from gotit.api.stt import SttUnavailable, stt_available, transcribe_audio
from gotit.api.verify_finalize import finalize_examine_with_gate
from gotit.api.workflow_persist import persist_workflow_exchange, teach_agent_text
from gotit.core.agents.echo import build_echo_agent, run_echo
from gotit.core.failure_lessons import learner_failure_hint
from gotit.core.models import TeachVerdict
from gotit.core.teach_verify import teach_examine_verdict
from gotit.db import ops as day_ops
from gotit.db import session_scope
from gotit.db.models import ClaimRow

router = APIRouter()

# Max upload for a single teach-back clip (no continuous recording).
_MAX_AUDIO_BYTES = 8 * 1024 * 1024


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
    claim_id: UUID | None = Field(
        default=None,
        description="When set and session closes, run Critic + deterministic gate.",
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


async def _finalize_teach_claim(
    *,
    claim_id: UUID,
    you_taught_well: bool,
    user_id: str,
    settings: Settings,
    answer: str | None,
    thread_id: UUID | None,
) -> dict[str, Any]:
    examine_verdict = teach_examine_verdict(you_taught_well)
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
            learner_answer=answer,
            user_id=user_id,
            settings=settings,
            thread_id=thread_id,
        )


async def _persist_teach(
    *,
    thread_id: UUID | None,
    user_id: str,
    topic: str,
    answer: str | None,
    verdict: TeachVerdict,
    claim_id: UUID | None = None,
    verify: dict[str, object] | None = None,
    gate_verdict: str | None = None,
) -> None:
    if thread_id is None:
        return
    extra: dict[str, object] = {"topic": topic, "session_done": verdict.done}
    if claim_id is not None:
        extra["claim_id"] = str(claim_id)
    display = gate_verdict
    if display is None and verdict.you_taught_well is not None:
        display = teach_examine_verdict(verdict.you_taught_well)
    if display is not None:
        extra["verdict"] = display
    if verify:
        extra.update(verify)
    if verify and gate_verdict:
        attach_verdict_blocks(
            extra,
            gate_verdict=str(gate_verdict),
            claim_id=claim_id,
        )
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
            title_seed=topic,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.get("/v1/teach/capabilities", dependencies=[Depends(require_api_key)])
async def teach_capabilities(
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    """Whether in-app recording transcription is available."""
    return {"stt_available": stt_available(settings)}


@router.post("/v1/teach/transcribe", dependencies=[Depends(require_api_key)])
async def teach_transcribe(
    settings: Annotated[Settings, Depends(get_settings)],
    file: Annotated[UploadFile, Field(alias="file")],
) -> dict[str, object]:
    """Audio → transcript for teach-back. Edit in UI before submitting."""
    if not stt_available(settings):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="STT not configured; paste or type the teach-back text instead",
        )
    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="empty audio"
        )
    if len(data) > _MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"audio too large (max {_MAX_AUDIO_BYTES} bytes)",
        )
    try:
        text = await transcribe_audio(
            data,
            filename=file.filename or "audio.webm",
            content_type=file.content_type,
            settings=settings,
        )
    except SttUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc
    return {"transcript": text}


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
        writeback: dict[str, object] | None = None
        verify: dict[str, object] | None = None
        gate_verdict: str | None = None
        if body.claim_id is not None:
            try:
                finalized = await _finalize_teach_claim(
                    claim_id=body.claim_id,
                    you_taught_well=body.you_taught_well,
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
        await _persist_teach(
            thread_id=body.thread_id,
            user_id=user_id,
            topic=body.topic,
            answer=body.answer,
            verdict=verdict,
            claim_id=body.claim_id,
            verify=verify,
            gate_verdict=gate_verdict,
        )
        out: dict[str, object] = {"verdict": verdict.model_dump(mode="json")}
        if writeback is not None:
            out["writeback"] = writeback
        if verify is not None:
            out["verify"] = verify
        return out

    async with session_scope() as session:
        prompt = await SessionPromptReader(session).get_active_prompt("echo")
        system_prompt = prompt.system_prompt if prompt else ""
        reader = SessionMemoryReader(session, user_id=user_id)
        agent = build_echo_agent(get_model(), system_prompt=system_prompt)
        lesson_block: str | None = None
        if body.claim_id is not None:
            claim_row = await session.get(ClaimRow, body.claim_id)
            if claim_row is not None and claim_row.user_id == user_id:
                lesson_block = await day_ops.build_failure_lesson_block(
                    session,
                    user_id=user_id,
                    claim_id=body.claim_id,
                    topic=claim_row.topic or body.topic,
                )
        verdict = await run_echo(
            agent,
            reader,
            topic=body.topic,
            history=body.history,
            answer=body.answer,
            failure_lesson_block=lesson_block,
        )
        failure_hint = learner_failure_hint(lesson_block)

    writeback = None
    verify = None
    gate_verdict = None
    if (
        verdict.done
        and verdict.you_taught_well is not None
        and body.claim_id is not None
    ):
        try:
            finalized = await _finalize_teach_claim(
                claim_id=body.claim_id,
                you_taught_well=verdict.you_taught_well,
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

    await _persist_teach(
        thread_id=body.thread_id,
        user_id=user_id,
        topic=body.topic,
        answer=body.answer,
        verdict=verdict,
        claim_id=body.claim_id,
        verify=verify,
        gate_verdict=gate_verdict,
    )
    result: dict[str, object] = {"verdict": verdict.model_dump(mode="json")}
    if writeback is not None:
        result["writeback"] = writeback
    if verify is not None:
        result["verify"] = verify
    if failure_hint:
        result["failure_hint"] = failure_hint
    return result
