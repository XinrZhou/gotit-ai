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
    examine_agent_text,
    persist_workflow_exchange,
)
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
from gotit.db.runtime import ensure_db
from gotit.mcp.app import mcp
from gotit.mcp.common import (
    _finalize_claim_mcp,
    _user_id,
    _verify_meta,
)


@mcp.tool()
async def gotit_ingest(material: str) -> dict[str, object]:
    """Ingest study material and return stub claims (Librarian not wired yet)."""
    await ensure_db()
    claim = day_ops.stub_extract_claim(material)
    async with session_scope() as session:
        session.add(
            ClaimRow(
                id=claim.id,
                user_id=_user_id(),
                text=claim.text,
                source_excerpt=claim.source_excerpt,
                status=claim.status.value,
                source_note_id=None,
                next_review_at=None,
            )
        )
    return {
        "claims": [claim.model_dump(mode="json")],
        "state": "claim",
        "note": "stub: claim extraction not wired yet",
    }

@mcp.tool()
async def gotit_examine(
    claim_id: str | None = None,
    topic: str | None = None,
    note_id: str | None = None,
    answer: str | None = None,
    history: list[dict[str, str]] | None = None,
    verdict: str | None = None,
    thread_id: str | None = None,
) -> dict[str, object]:
    """Examine a claim (multi-turn). Pass `note_id` for note-session mode or
    `topic` for topic-session mode (Axiom shuttles across the claims); pass
    `verdict` to bypass the agent (stub/tests, single-claim mode only).
    Optional `thread_id` appends turns to the companion thread stream.

    Claim-close runs Critic + deterministic gate via shared finalize (REST parity).
    """
    await ensure_db()
    settings = get_settings()
    user_id = _user_id()
    tid = UUID(thread_id) if thread_id else None

    async def _persist(
        *,
        agent_text: str,
        extra: dict[str, object],
        title_seed: str | None = None,
    ) -> dict[str, object] | None:
        if tid is None:
            return None
        seed = title_seed or str(extra.get("topic") or "") or None
        try:
            await persist_workflow_exchange(
                thread_id=tid,
                user_id=user_id,
                workflow="examine",
                agent_text=agent_text,
                user_text=answer,
                extra_metadata=extra,
                title_seed=seed,
            )
        except KeyError as exc:
            return {"error": str(exc)}
        return None

    # --- Claims-session mode (note_id or topic) ---
    if note_id is not None or topic is not None:
        async with session_scope() as session:
            if note_id is not None:
                claims = await day_ops.list_note_claims(
                    session, UUID(note_id), user_id=user_id
                )
            elif topic is not None:
                claims = await day_ops.list_topic_claims_today(
                    session, topic, user_id=user_id
                )
        if not settings.llm_api_key:
            session_result = stub_topic_examine(
                claims=claims, answer=answer, history=history
            )
        else:
            async with session_scope() as session:
                from gotit.db.ops.graph import build_budget_subgraph
                from gotit.db.ops.memory import build_failure_lesson_block

                lesson_block: str | None = None
                budget_block: str | None = None
                if claims:
                    focus = claims[0]
                    budget = await build_budget_subgraph(
                        session, user_id=user_id, claim_id=focus.id
                    )
                    budget_block = budget.prompt_block
                    neighbor_ids = list(budget.confused_claim_ids)
                    for c in claims[1:]:
                        if c.id not in neighbor_ids:
                            neighbor_ids.append(c.id)
                    lesson_block = await build_failure_lesson_block(
                        session,
                        user_id=user_id,
                        claim_id=focus.id,
                        topic=topic or focus.topic,
                        neighbor_claim_ids=neighbor_ids,
                    )
                prompt = await SessionPromptReader(session).get_active_prompt("axiom")
                system_prompt = prompt.system_prompt if prompt else ""
                reader = SessionMemoryReader(session, user_id=user_id)
                claims_agent = build_topic_axiom_agent(
                    get_model(), system_prompt=system_prompt
                )
            session_result = await run_topic_examine(
                claims_agent,
                reader,
                topic=topic or "",
                claims=claims,
                history=history or [],
                answer=answer,
                failure_lesson_block=lesson_block,
                budget_block=budget_block,
            )
        writeback: dict[str, object] | None = None
        verify: dict[str, object] | None = None
        gate_verdict = session_result.verdict
        if (
            session_result.done
            and session_result.verdict is not None
            and session_result.current_claim_id
        ):
            try:
                finalized = await _finalize_claim_mcp(
                    claim_id=session_result.current_claim_id,
                    examine_verdict=session_result.verdict,
                    user_id=user_id,
                    settings=settings,
                    answer=answer,
                    thread_id=tid,
                )
            except KeyError as exc:
                return {"error": str(exc)}
            writeback = finalized["writeback"]  # type: ignore[assignment]
            verify = _verify_meta(finalized)
            gate_verdict = finalized["gate_verdict"]  # type: ignore[assignment]
        extra: dict[str, object] = {"session_done": session_result.session_done}
        if note_id is not None:
            extra["note_id"] = note_id
        if topic is not None:
            extra["topic"] = topic
        if session_result.current_claim_id:
            extra["claim_id"] = str(session_result.current_claim_id)
        if gate_verdict:
            extra["verdict"] = gate_verdict
        if verify:
            extra.update(verify)
        if verify and gate_verdict:
            attach_verdict_blocks(
                extra,
                gate_verdict=str(gate_verdict),
                claim_id=session_result.current_claim_id,
            )
        session_seed = (topic or "").strip() or (
            claims[0].text if claims else None
        )
        err = await _persist(
            agent_text=examine_agent_text(
                follow_up=session_result.follow_up,
                done=session_result.done,
                verdict=gate_verdict if session_result.done else session_result.verdict,
            ),
            extra=extra,
            title_seed=session_seed,
        )
        if err:
            return err
        verdict_payload = session_result.model_dump(mode="json")
        if gate_verdict is not None and session_result.done:
            verdict_payload["verdict"] = gate_verdict
        out: dict[str, object] = {
            "verdict": verdict_payload,
            "writeback": writeback,
        }
        if verify:
            out["verify"] = verify
        return out

    # --- Single-claim mode ---
    if claim_id is None:
        return {"error": "one of `note_id`, `topic`, or `claim_id` is required"}

    if verdict is not None:
        try:
            finalized = await _finalize_claim_mcp(
                claim_id=UUID(claim_id),
                examine_verdict=verdict,
                user_id=user_id,
                settings=settings,
                answer=answer,
                thread_id=tid,
            )
        except KeyError as exc:
            return {"error": str(exc)}
        except ValueError as exc:
            return {"error": str(exc)}
        verify = _verify_meta(finalized)
        extra_direct: dict[str, object] = {
            "claim_id": claim_id,
            "session_done": True,
            **verify,
        }
        attach_verdict_blocks(
            extra_direct,
            gate_verdict=str(finalized["gate_verdict"]),
            claim_id=claim_id,
        )
        err = await _persist(
            agent_text=examine_agent_text(
                follow_up="", done=True, verdict=str(finalized["gate_verdict"])
            ),
            extra=extra_direct,
        )
        if err:
            return err
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

    async with session_scope() as session:
        claim = await session.get(ClaimRow, UUID(claim_id))
        if claim is None or claim.user_id != user_id:
            return {"error": f"claim not found: {claim_id}"}
        from gotit.db.ops.graph import build_budget_subgraph
        from gotit.db.ops.memory import build_failure_lesson_block

        budget = await build_budget_subgraph(
            session, user_id=user_id, claim_id=UUID(claim_id)
        )
        lesson_block = await build_failure_lesson_block(
            session,
            user_id=user_id,
            claim_id=UUID(claim_id),
            topic=claim.topic,
            neighbor_claim_ids=budget.confused_claim_ids,
        )
        prompt = await SessionPromptReader(session).get_active_prompt("axiom")
        system_prompt = prompt.system_prompt if prompt else ""
        reader = SessionMemoryReader(session, user_id=user_id)
        agent = build_axiom_agent(get_model(), system_prompt=system_prompt)
        result = await run_axiom(
            agent,
            reader,
            claim_text=claim.text,
            history=history or [],
            answer=answer,
            budget_block=budget.prompt_block,
            failure_lesson_block=lesson_block,
        )

    writeback = None
    verify = None
    gate_verdict = result.verdict
    if result.done and result.verdict is not None:
        try:
            finalized = await _finalize_claim_mcp(
                claim_id=UUID(claim_id),
                examine_verdict=result.verdict,
                examine_score=result.score,
                examine_evidence=result.evidence,
                user_id=user_id,
                settings=settings,
                answer=answer,
                thread_id=tid,
            )
        except KeyError as exc:
            return {"error": str(exc)}
        wb = finalized.get("writeback")
        writeback = wb if isinstance(wb, dict) else None
        verify = _verify_meta(finalized)
        raw_gate = finalized.get("gate_verdict")
        gate_verdict = (
            raw_gate if raw_gate in {"passed", "almost", "owe_next"} else None
        )
    extra_single: dict[str, object] = {
        "claim_id": claim_id,
        "session_done": bool(result.done),
    }
    if gate_verdict:
        extra_single["verdict"] = gate_verdict
    if verify:
        extra_single.update(verify)
    if verify and gate_verdict:
        attach_verdict_blocks(
            extra_single,
            gate_verdict=str(gate_verdict),
            claim_id=claim_id,
        )
    err = await _persist(
        agent_text=examine_agent_text(
            follow_up=result.follow_up,
            done=result.done,
            verdict=gate_verdict if result.done else result.verdict,
        ),
        extra=extra_single,
        title_seed=claim.text,
    )
    if err:
        return err
    verdict_out = result.model_dump(mode="json")
    if gate_verdict is not None and result.done:
        verdict_out["verdict"] = gate_verdict
    out_single: dict[str, object] = {
        "verdict": verdict_out,
        "writeback": writeback,
    }
    if verify:
        out_single["verify"] = verify
    return out_single

@mcp.tool()
async def gotit_start_verify(
    thread_id: str, claim_id: str, answer: str | None = None, examine_verdict: str | None = None
) -> dict[str, object]:
    """Run the verify-loop (examine → recheck → gate) for one claim in a thread.

    The gate is deterministic code (no LLM): stricter of examiner's and critic's
    verdicts. Recheck + gate + writeback share finalize with REST / examine.
    """
    from gotit.api.verify_attempt import run_verify_attempt

    await ensure_db()
    settings = get_settings()
    user_id = _user_id()

    async with session_scope() as session:
        tid = UUID(thread_id)
        cid = UUID(claim_id)
        claim = await session.get(ClaimRow, cid)
        if claim is None or claim.user_id != user_id:
            return {"error": "claim not found"}

        try:
            return await run_verify_attempt(
                session,
                thread_id=tid,
                claim=claim,
                user_id=user_id,
                settings=settings,
                answer=answer,
                examine_verdict=examine_verdict,
            )
        except KeyError as exc:
            return {"error": str(exc)}

