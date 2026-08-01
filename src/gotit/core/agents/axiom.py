"""Axiom — the examiner agent.

Multi-turn: each call returns an `ExamineVerdict`. When `done=false`, `follow_up`
is the next question to ask the learner. When `done=true`, `verdict` is one of
`passed | almost | owe_next` and the orchestration layer writes back via
`db.ops.apply_examine_verdict`.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.exceptions import AgentRunError, UnexpectedModelBehavior

from gotit.core.agents.deps import MemoryReader
from gotit.core.models import Claim, ExamineVerdict, MemoryEntry, TopicExamineVerdict

AxiomAgent = Agent[Any, ExamineVerdict]
TopicAxiomAgent = Agent[Any, TopicExamineVerdict]


def build_axiom_agent(model: Any, *, system_prompt: str) -> AxiomAgent:
    return Agent(
        model,
        output_type=ExamineVerdict,
        system_prompt=system_prompt,
        name="axiom",
        retries=2,
    )


def build_topic_axiom_agent(model: Any, *, system_prompt: str) -> TopicAxiomAgent:
    return Agent(
        model,
        output_type=TopicExamineVerdict,
        system_prompt=system_prompt,
        name="axiom-topic",
        retries=2,
    )


def _format_history(history: list[dict[str, str]]) -> str:
    if not history:
        return "(none yet)"
    lines = []
    for turn in history:
        role = "Examiner" if turn.get("role") == "examiner" else "Learner"
        lines.append(f"{role}: {turn.get('text', '')}")
    return "\n".join(lines)


def _format_memory(memory: list[MemoryEntry]) -> str:
    if not memory:
        return "(none)"
    return "\n".join(f"- [{m.kind}] {m.topic or '-'}: {m.content}" for m in memory[:8])


def _extract_json_object(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def _fallback_examine(*, claim_text: str) -> ExamineVerdict:
    snippet = claim_text.strip().replace("\n", " ")
    if len(snippet) > 72:
        snippet = snippet[:72] + "…"
    return ExamineVerdict(
        done=False,
        verdict=None,
        follow_up=f"先用自己的话说说：「{snippet}」到底是什么意思？",
    )


def _error_follow_up(exc: BaseException) -> str:
    """Pass through the model/gateway error text (trimmed) as the chat reply."""
    text = str(exc).strip() or type(exc).__name__
    # Keep one short line for the bubble.
    return text.split("\n", 1)[0][:400]


def _fallback_topic(*, claims: list[Claim]) -> TopicExamineVerdict:
    first = claims[0]
    return TopicExamineVerdict(
        current_claim_id=first.id,
        done=False,
        verdict=None,
        follow_up=(
            f"我们来测这一条：「{first.text}」。"
            "你能用自己的话说说，它到底指什么？"
        ),
        session_done=False,
    )


def _recover_examine(body: str | None, *, claim_text: str) -> ExamineVerdict:
    data = _extract_json_object(body or "")
    if data is not None:
        try:
            return ExamineVerdict.model_validate(data)
        except Exception:
            pass
    return _fallback_examine(claim_text=claim_text)


def _recover_topic(body: str | None, *, claims: list[Claim]) -> TopicExamineVerdict:
    data = _extract_json_object(body or "")
    if data is not None:
        try:
            return TopicExamineVerdict.model_validate(data)
        except Exception:
            pass
    return _fallback_topic(claims=claims)


def build_prompt(
    *,
    claim_text: str,
    history: list[dict[str, str]],
    answer: str | None,
    memory: list[MemoryEntry],
    trajectory: list[MemoryEntry] | None = None,
    budget_block: str | None = None,
    failure_lesson_block: str | None = None,
) -> str:
    from gotit.core.context_budget import compose_examine_context

    composed = compose_examine_context(budget_block, failure_lesson_block)
    parts = [
        f"## Claim under examination\n{claim_text}",
        f"## Relevant memory about this learner\n{_format_memory(memory)}",
    ]
    if trajectory:
        parts.append(
            "## Prior attempts on this topic (learning trajectory)\n"
            + _format_memory(trajectory)
        )
    if composed.budget_block:
        parts.append(composed.budget_block)
    if composed.failure_lesson_block:
        parts.append(composed.failure_lesson_block)
    parts.append(f"## Conversation so far\n{_format_history(history)}")
    if answer:
        parts.append(f"## Learner's latest answer\n{answer}")
    parts.append(
        "Respond with structured fields only (no prose outside the schema). "
        "Decide: ask the next probing question (done=false, verdict=null), or "
        "deliver a verdict (done=true, verdict in passed|almost|owe_next). "
        "Put the next question in `follow_up`; on the final turn set follow_up "
        "to a one-line summary. "
        "If the learner said they don't know or asked you to answer, do NOT "
        "repeat the previous question — give a short scaffold in follow_up "
        "and either ask a different check or deliver almost/owe_next."
    )
    return "\n\n".join(parts)


async def run_axiom(
    agent: AxiomAgent,
    memory: MemoryReader,
    *,
    claim_text: str,
    history: list[dict[str, str]] | None = None,
    answer: str | None = None,
    trajectory: list[MemoryEntry] | None = None,
    budget_block: str | None = None,
    failure_lesson_block: str | None = None,
) -> ExamineVerdict:
    entries = await memory.list_memory(layer="working", limit=10)
    prompt = build_prompt(
        claim_text=claim_text,
        history=list(history or []),
        answer=answer,
        memory=entries,
        trajectory=trajectory,
        budget_block=budget_block,
        failure_lesson_block=failure_lesson_block,
    )
    try:
        result = await agent.run(prompt)
        return result.output
    except UnexpectedModelBehavior as exc:
        return _recover_examine(getattr(exc, "body", None), claim_text=claim_text)
    except AgentRunError as exc:
        # Surface the model/gateway error as follow_up instead of 500.
        return ExamineVerdict(done=False, verdict=None, follow_up=_error_follow_up(exc))
    except Exception as exc:
        return ExamineVerdict(done=False, verdict=None, follow_up=_error_follow_up(exc))


def _format_claims(claims: list[Claim]) -> str:
    if not claims:
        return "(none)"
    return "\n".join(f"- [{c.id}] {c.text}" for c in claims)


def build_topic_prompt(
    *,
    topic: str,
    claims: list[Claim],
    history: list[dict[str, str]],
    answer: str | None,
    memory: list[MemoryEntry],
    failure_lesson_block: str | None = None,
    budget_block: str | None = None,
) -> str:
    parts = [
        f"## Topic\n{topic}",
        f"## Claims to examine (id + text)\n{_format_claims(claims)}",
        f"## Relevant memory about this learner\n{_format_memory(memory)}",
    ]
    if budget_block:
        parts.append(budget_block)
    if failure_lesson_block:
        parts.append(failure_lesson_block)
    parts.append(f"## Conversation so far\n{_format_history(history)}")
    if answer:
        parts.append(f"## Learner's latest answer\n{answer}")
    parts.append(
        "Respond with structured fields only (no prose outside the schema). "
        "You are examining the learner across multiple claims in this topic, ONE at a time. "
        "Each turn, decide:\n"
        "- Keep probing the current claim: done=false, verdict=null, current_claim_id=the "
        "claim you are asking about.\n"
        "- Deliver a verdict for the current claim: done=true, verdict in "
        "passed|almost|owe_next, current_claim_id=the judged claim. Then immediately move "
        "to the next claim's opening question in `follow_up`, unless all claims are done — "
        "then set session_done=true and put a one-line summary in follow_up.\n"
        "Always set current_claim_id to the claim this turn is about. Put the next question "
        "in follow_up. Ask ONE question at a time; never dump a list. "
        "If the learner said they don't know or asked you to answer, do NOT "
        "repeat the previous question — short scaffold, then a different check "
        "or almost/owe_next."
    )
    return "\n\n".join(parts)


async def run_topic_examine(
    agent: TopicAxiomAgent,
    memory: MemoryReader,
    *,
    topic: str,
    claims: list[Claim],
    history: list[dict[str, str]] | None = None,
    answer: str | None = None,
    failure_lesson_block: str | None = None,
    budget_block: str | None = None,
) -> TopicExamineVerdict:
    if not claims:
        return TopicExamineVerdict(
            current_claim_id=None,
            done=False,
            verdict=None,
            follow_up="该主题暂无待考的题。",
            session_done=True,
        )
    entries = await memory.list_memory(layer="working", limit=10)
    prompt = build_topic_prompt(
        topic=topic,
        claims=claims,
        history=list(history or []),
        answer=answer,
        memory=entries,
        failure_lesson_block=failure_lesson_block,
        budget_block=budget_block,
    )
    try:
        result = await agent.run(prompt)
        return result.output
    except UnexpectedModelBehavior as exc:
        return _recover_topic(getattr(exc, "body", None), claims=claims)
    except AgentRunError as exc:
        first = claims[0]
        return TopicExamineVerdict(
            current_claim_id=first.id,
            done=False,
            verdict=None,
            follow_up=_error_follow_up(exc),
            session_done=False,
        )
    except Exception as exc:
        first = claims[0]
        return TopicExamineVerdict(
            current_claim_id=first.id,
            done=False,
            verdict=None,
            follow_up=_error_follow_up(exc),
            session_done=False,
        )


def stub_topic_examine(
    *,
    claims: list[Claim],
    answer: str | None,
    history: list[dict[str, str]] | None,
) -> TopicExamineVerdict:
    """No-LLM fallback: each answer passes the current claim, then advance."""
    if not claims:
        return TopicExamineVerdict(
            current_claim_id=None,
            done=False,
            verdict=None,
            follow_up="该主题暂无待考的题。",
            session_done=True,
        )
    user_turns = sum(1 for m in (history or []) if m.get("role") == "user")
    if answer is None:
        first = claims[0]
        return TopicExamineVerdict(
            current_claim_id=first.id,
            done=False,
            verdict=None,
            follow_up=(
                f"我们来测这一条：「{first.text}」。"
                "你能用自己的话说说，它到底指什么？为什么是对的？"
            ),
            session_done=False,
        )
    judged = claims[user_turns] if user_turns < len(claims) else claims[-1]
    next_index = user_turns + 1
    if next_index < len(claims):
        nxt = claims[next_index]
        follow_up = f"这一条过了。下一题：「{nxt.text}」。说说你的理解？"
        session_done = False
    else:
        follow_up = "本主题的题都过了 ✓"
        session_done = True
    return TopicExamineVerdict(
        current_claim_id=judged.id,
        done=True,
        verdict="passed",
        follow_up=follow_up,
        session_done=session_done,
    )
