"""Compass — the curator agent.

Given a study note, extracts testable claims (with topic/tags) and recommends
which claims are worth today's attention given the learner's recent weaknesses.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import Agent

from gotit.core.agents.deps import MemoryReader
from gotit.core.models import CompassOutput, MemoryEntry

CompassAgent = Agent[Any, CompassOutput]


def build_compass_agent(model: Any, *, system_prompt: str) -> CompassAgent:
    return Agent(
        model,
        output_type=CompassOutput,
        system_prompt=system_prompt,
        name="compass",
    )


def _format_memory(memory: list[MemoryEntry]) -> str:
    if not memory:
        return "(no prior weaknesses recorded)"
    return "\n".join(f"- [{m.kind}] {m.topic or '-'}: {m.content}" for m in memory[:10])


def build_prompt(*, note_body: str, memory: list[MemoryEntry]) -> str:
    return (
        f"## Learner's study note\n{note_body}\n\n"
        f"## Recent weaknesses / context\n{_format_memory(memory)}\n\n"
        "Extract the testable claims and recommend 1–2 for today. "
        "Return claims with a short topic and up to 5 tags each."
    )


async def run_compass(
    agent: CompassAgent,
    memory: MemoryReader,
    *,
    note_body: str,
) -> CompassOutput:
    entries = await memory.list_memory(layer="long", limit=10)
    prompt = build_prompt(note_body=note_body, memory=entries)
    result = await agent.run(prompt)
    return result.output
