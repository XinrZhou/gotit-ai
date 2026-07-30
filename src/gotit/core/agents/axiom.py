"""Axiom — the examiner agent.

Multi-turn: each call returns an `ExamineVerdict`. When `done=false`, `follow_up`
is the next question to ask the learner. When `done=true`, `verdict` is one of
`passed | almost | owe_next` and the orchestration layer writes back via
`db.ops.apply_examine_verdict`.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import Agent

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
    )


def build_topic_axiom_agent(model: Any, *, system_prompt: str) -> TopicAxiomAgent:
    return Agent(
        model,
        output_type=TopicExamineVerdict,
        system_prompt=system_prompt,
        name="axiom-topic",
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
    parts = [
        f"## Claim under examination\n{claim_text}",
        f"## Relevant memory about this learner\n{_format_memory(memory)}",
    ]
    if trajectory:
        parts.append(
            "## Prior attempts on this topic (learning trajectory)\n"
            + _format_memory(trajectory)
        )
    if budget_block:
        parts.append(budget_block)
    if failure_lesson_block:
        parts.append(failure_lesson_block)
    parts.append(f"## Conversation so far\n{_format_history(history)}")
    if answer:
        parts.append(f"## Learner's latest answer\n{answer}")
    parts.append(
        "Decide: ask the next probing question (done=false, verdict=null), or "
        "deliver a verdict (done=true, verdict in passed|almost|owe_next). "
        "Put the next question in `follow_up`; on the final turn set follow_up "
        "to a one-line summary."
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
    result = await agent.run(prompt)
    return result.output


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
) -> str:
    parts = [
        f"## Topic\n{topic}",
        f"## Claims to examine (id + text)\n{_format_claims(claims)}",
        f"## Relevant memory about this learner\n{_format_memory(memory)}",
    ]
    if failure_lesson_block:
        parts.append(failure_lesson_block)
    parts.append(f"## Conversation so far\n{_format_history(history)}")
    if answer:
        parts.append(f"## Learner's latest answer\n{answer}")
    parts.append(
        "You are examining the learner across multiple claims in this topic, ONE at a time. "
        "Each turn, decide:\n"
        "- Keep probing the current claim: done=false, verdict=null, current_claim_id=the "
        "claim you are asking about.\n"
        "- Deliver a verdict for the current claim: done=true, verdict in "
        "passed|almost|owe_next, current_claim_id=the judged claim. Then immediately move "
        "to the next claim's opening question in `follow_up`, unless all claims are done — "
        "then set session_done=true and put a one-line summary in follow_up.\n"
        "Always set current_claim_id to the claim this turn is about. Put the next question "
        "in follow_up. Ask ONE question at a time; never dump a list."
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
    )
    result = await agent.run(prompt)
    return result.output


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
