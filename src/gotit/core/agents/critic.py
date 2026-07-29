"""Critic — the recheck officer.

Given Axiom's examine verdict on a claim (plus the learner's last answer), Critic
independently re-checks from a stricter, edge-case-focused angle and returns its
own verdict. The deterministic gate then takes the stricter of the two. This
enforces "no agent reviews its own judgment" — the recheck agent differs from the
examiner and uses a different rubric.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import Agent

from gotit.core.agents.deps import MemoryReader
from gotit.core.models import MemoryEntry, RecheckVerdict

CriticAgent = Agent[Any, RecheckVerdict]


def build_critic_agent(model: Any, *, system_prompt: str) -> CriticAgent:
    return Agent(
        model,
        output_type=RecheckVerdict,
        system_prompt=system_prompt,
        name="critic",
    )


def _format_memory(memory: list[MemoryEntry]) -> str:
    if not memory:
        return "(none)"
    return "\n".join(f"- [{m.kind}] {m.topic or '-'}: {m.content}" for m in memory[:8])


def build_prompt(
    *,
    claim_text: str,
    examine_verdict: str,
    examine_score: float | None,
    examine_evidence: str | None,
    learner_answer: str | None,
    memory: list[MemoryEntry],
) -> str:
    parts = [
        f"## Claim under recheck\n{claim_text}",
        f"## Axiom's verdict\nverdict={examine_verdict} score={examine_score} "
        f"evidence={examine_evidence or '(none)'}",
        f"## Relevant memory\n{_format_memory(memory)}",
    ]
    if learner_answer:
        parts.append(f"## Learner's last answer\n{learner_answer}")
    parts.append(
        "Return your independent recheck verdict (passed|almost|owe_next) and a "
        "one-line reason. Be stricter than Axiom on edge cases."
    )
    return "\n\n".join(parts)


async def run_critic(
    agent: CriticAgent,
    memory: MemoryReader,
    *,
    claim_text: str,
    examine_verdict: str,
    examine_score: float | None = None,
    examine_evidence: str | None = None,
    learner_answer: str | None = None,
) -> RecheckVerdict:
    entries = await memory.list_memory(layer="long", limit=8)
    prompt = build_prompt(
        claim_text=claim_text,
        examine_verdict=examine_verdict,
        examine_score=examine_score,
        examine_evidence=examine_evidence,
        learner_answer=learner_answer,
        memory=entries,
    )
    result = await agent.run(prompt)
    return result.output


def stub_critic(*, examine_verdict: str) -> RecheckVerdict:
    """No-LLM fallback: echo the examiner's verdict (neutral recheck)."""
    return RecheckVerdict(
        verdict=examine_verdict,  # type: ignore[arg-type]
        reason=f"无 LLM key，复核采用 Axiom 判定 {examine_verdict}",
    )
