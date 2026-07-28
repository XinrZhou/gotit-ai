"""Echo — the teach-back agent.

Independent multi-turn mode: the learner explains a topic as if teaching it.
Echo asks one clarifying/stress-test question per turn and, on the final turn,
returns whether the teaching held plus the gaps it found.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import Agent

from gotit.core.agents.deps import MemoryReader
from gotit.core.models import MemoryEntry, TeachVerdict

EchoAgent = Agent[Any, TeachVerdict]


def build_echo_agent(model: Any, *, system_prompt: str) -> EchoAgent:
    return Agent(
        model,
        output_type=TeachVerdict,
        system_prompt=system_prompt,
        name="echo",
    )


def _format_history(history: list[dict[str, str]]) -> str:
    if not history:
        return "(none yet)"
    lines = []
    for turn in history:
        role = "Echo" if turn.get("role") == "examiner" else "Learner"
        lines.append(f"{role}: {turn.get('text', '')}")
    return "\n".join(lines)


def _format_memory(memory: list[MemoryEntry]) -> str:
    if not memory:
        return "(none)"
    return "\n".join(f"- [{m.kind}] {m.topic or '-'}: {m.content}" for m in memory[:8])


def build_prompt(
    *,
    topic: str,
    history: list[dict[str, str]],
    answer: str | None,
    memory: list[MemoryEntry],
) -> str:
    parts = [
        f"## Topic the learner is teaching back\n{topic}",
        f"## Relevant memory\n{_format_memory(memory)}",
        f"## Conversation so far\n{_format_history(history)}",
    ]
    if answer:
        parts.append(f"## Learner's latest answer\n{answer}")
    parts.append(
        "Decide: ask one clarifying or stress-test question (done=false, "
        "next_question set, you_taught_well=null), or deliver a verdict "
        "(done=true, you_taught_well bool, gaps list, next_question null)."
    )
    return "\n\n".join(parts)


async def run_echo(
    agent: EchoAgent,
    memory: MemoryReader,
    *,
    topic: str,
    history: list[dict[str, str]] | None = None,
    answer: str | None = None,
) -> TeachVerdict:
    entries = await memory.list_memory(layer="long", limit=8)
    prompt = build_prompt(
        topic=topic,
        history=list(history or []),
        answer=answer,
        memory=entries,
    )
    result = await agent.run(prompt)
    return result.output
