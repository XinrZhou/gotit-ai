from __future__ import annotations

from uuid import UUID

from gotit.api.action_blocks import attach_verdict_blocks
from gotit.api.deps import (
    SessionMemoryReader,
    SessionPromptReader,
    get_model,
)
from gotit.api.settings import get_settings
from gotit.api.workflow_persist import (
    persist_workflow_exchange,
    teach_agent_text,
)
from gotit.core.agents.echo import build_echo_agent, run_echo
from gotit.core.failure_lessons import learner_failure_hint
from gotit.core.models import (
    TeachVerdict,
)
from gotit.db import ops as day_ops
from gotit.db import session_scope
from gotit.db.models import ClaimRow
from gotit.db.runtime import ensure_db
from gotit.mcp.app import mcp
from gotit.mcp.common import (
    _finalize_claim_mcp,
    _user_id,
    _verify_meta,
)


@mcp.tool()
async def gotit_teach(
    topic: str,
    answer: str | None = None,
    history: list[dict[str, str]] | None = None,
    you_taught_well: bool | None = None,
    claim_id: str | None = None,
    thread_id: str | None = None,
) -> dict[str, object]:
    """Teach-back mode (Echo). Pass `you_taught_well` to bypass the agent (stub/tests).
    Optional `claim_id` on close runs Critic + deterministic gate (REST parity).
    Optional `thread_id` appends turns to the companion thread stream."""
    from gotit.core.teach_verify import teach_examine_verdict

    await ensure_db()
    settings = get_settings()
    user_id = _user_id()
    tid = UUID(thread_id) if thread_id else None
    cid = UUID(claim_id) if claim_id else None

    async def _persist(
        verdict: TeachVerdict,
        *,
        verify: dict[str, object] | None = None,
        gate_verdict: str | None = None,
        failure_hint: str | None = None,
    ) -> dict[str, object] | None:
        if tid is None:
            return None
        extra: dict[str, object] = {"topic": topic, "session_done": verdict.done}
        if cid is not None:
            extra["claim_id"] = str(cid)
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
                claim_id=cid,
            )
        if failure_hint and not answer:
            extra["failure_hint"] = failure_hint
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
                title_seed=topic,
            )
        except KeyError as exc:
            return {"error": str(exc)}
        return None

    async def _maybe_finalize(
        you_taught: bool,
    ) -> tuple[dict[str, object] | None, dict[str, object] | None, str | None]:
        if cid is None:
            return None, None, None
        try:
            finalized = await _finalize_claim_mcp(
                claim_id=cid,
                examine_verdict=teach_examine_verdict(you_taught),
                user_id=user_id,
                settings=settings,
                answer=answer,
                thread_id=tid,
            )
        except KeyError as exc:
            return {"error": str(exc)}, None, None  # type: ignore[return-value]
        verify = _verify_meta(finalized)
        return finalized["writeback"], verify, finalized["gate_verdict"]  # type: ignore[return-value]

    if you_taught_well is not None:
        verdict = TeachVerdict(
            done=True,
            you_taught_well=you_taught_well,
            gaps=[],
            next_question=None,
        )
        writeback, verify, gate_verdict = await _maybe_finalize(you_taught_well)
        if isinstance(writeback, dict) and writeback.get("error"):
            return writeback
        err = await _persist(verdict, verify=verify, gate_verdict=gate_verdict)
        if err:
            return err
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
        if cid is not None:
            claim_row = await session.get(ClaimRow, cid)
            if claim_row is not None and claim_row.user_id == user_id:
                lesson_block = await day_ops.build_failure_lesson_block(
                    session,
                    user_id=user_id,
                    claim_id=cid,
                    topic=claim_row.topic or topic,
                )
        verdict = await run_echo(
            agent,
            reader,
            topic=topic,
            history=history or [],
            answer=answer,
            failure_lesson_block=lesson_block,
        )
        failure_hint = learner_failure_hint(lesson_block)

    writeback = None
    verify = None
    gate_verdict = None
    if verdict.done and verdict.you_taught_well is not None and cid is not None:
        writeback, verify, gate_verdict = await _maybe_finalize(verdict.you_taught_well)
        if isinstance(writeback, dict) and writeback.get("error"):
            return writeback
    err = await _persist(
        verdict,
        verify=verify,
        gate_verdict=gate_verdict,
        failure_hint=failure_hint,
    )
    if err:
        return err
    result: dict[str, object] = {"verdict": verdict.model_dump(mode="json")}
    if writeback is not None:
        result["writeback"] = writeback
    if verify is not None:
        result["verify"] = verify
    if failure_hint:
        result["failure_hint"] = failure_hint
    return result

