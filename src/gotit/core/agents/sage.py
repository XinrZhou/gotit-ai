"""Sage — the interviewer agent (resume-driven drill).

Multi-turn: simulates an interviewer of a chosen round (tech_1~4 / hr) deep-
diving the candidate's resume (+ imported drill materials, optional project
focus, optional direction hint). Each call returns a `SageVerdict`. When
`done=false`, `follow_up` is the next question. When `done=true`, `gaps` lists
the weak points found.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import Agent

from gotit.core.agents.deps import MemoryReader
from gotit.core.models import (
    DrillMaterial,
    DrillRound,
    MemoryEntry,
    Project,
    ResumeDocument,
    SageVerdict,
)

SageAgent = Agent[Any, SageVerdict]


def build_sage_agent(model: Any, *, system_prompt: str) -> SageAgent:
    return Agent(
        model,
        output_type=SageVerdict,
        system_prompt=system_prompt,
        name="sage",
    )


def _format_history(history: list[dict[str, str]]) -> str:
    if not history:
        return "(none yet)"
    lines = []
    for turn in history:
        role = "Sage" if turn.get("role") == "examiner" else "Candidate"
        lines.append(f"{role}: {turn.get('text', '')}")
    return "\n".join(lines)


def _format_memory(memory: list[MemoryEntry]) -> str:
    if not memory:
        return "(none)"
    return "\n".join(f"- [{m.kind}] {m.topic or '-'}: {m.content}" for m in memory[:8])


def _format_resume(resume: ResumeDocument) -> str:
    parts: list[str] = []
    b = resume.basics
    if b.name or b.target_role:
        parts.append(
            f"candidate: {b.name or '-'} / target: {b.target_role or '-'}"
        )
    parts.append("projects:")
    for p in resume.projects:
        line = f"- {p.name}"
        if p.role:
            line += f" (role: {p.role})"
        if p.goal:
            line += f" — {p.goal}"
        if p.tech_stack:
            line += f" | tech: {', '.join(p.tech_stack)}"
        if p.description:
            line += f"\n    {p.description}"
        parts.append(line)
    return "\n".join(parts) if parts else "(no projects parsed)"


def _format_materials(materials: list[DrillMaterial]) -> str:
    if not materials:
        return "(none)"
    return "\n".join(f"- {m.title}\n  {m.body}" for m in materials)


def _format_project(project: Project | None) -> str:
    if project is None:
        return "(resume-level, no single project focus)"
    parts = [f"name: {project.name}"]
    if project.role:
        parts.append(f"role: {project.role}")
    if project.goal:
        parts.append(f"goal: {project.goal}")
    if project.tech_stack:
        parts.append(f"tech_stack: {', '.join(project.tech_stack)}")
    return "\n".join(parts)


_ROUND_GUIDE = {
    DrillRound.TECH_1: (
        "技术一面：先把项目讲清楚，偏广度。让候选人介绍项目、角色、技术栈，"
        "问 1-2 层基础选型即可，不深挖架构。"
    ),
    DrillRound.TECH_2: (
        "技术二面：深度追问 + 系统设计。按 drill ladder 走 3-5 层："
        "tech choice → why → scale 100x → failure mode → metrics。"
    ),
    DrillRound.TECH_3: (
        "技术三面：架构 / 跨项目。追问架构权衡、跨项目一致性、技术领导力取舍。"
    ),
    DrillRound.TECH_4: (
        "技术四面（资深终面）：偏技术领导力、取舍、长期演进。问最深的架构与组织级决策。"
    ),
    DrillRound.HR: (
        "HR 面：行为面（STAR）+ 职业规划 + 软技能。不追问技术细节，"
        "问动机、协作、冲突处理、成长。"
    ),
}


def build_prompt(
    *,
    resume: ResumeDocument,
    materials: list[DrillMaterial],
    project: Project | None,
    round_: DrillRound,
    direction: str | None,
    history: list[dict[str, str]],
    answer: str | None,
    memory: list[MemoryEntry],
) -> str:
    parts = [
        f"## Interview round\n{round_.value} — {_ROUND_GUIDE[round_]}",
        f"## Candidate's resume\n{_format_resume(resume)}",
    ]
    if project is not None:
        parts.append(f"## Focused project\n{_format_project(project)}")
    parts.append(f"## Candidate's deep-dive materials\n{_format_materials(materials)}")
    parts.append(f"## Relevant memory about this learner\n{_format_memory(memory)}")
    parts.append(f"## Conversation so far\n{_format_history(history)}")
    if answer:
        parts.append(f"## Candidate's latest answer\n{answer}")
    if direction:
        parts.append(f"## Direction hint\n候选人希望本轮偏：{direction}。请据此调整追问侧重。")
    parts.append(
        "Decide: ask the next question (done=false, follow_up set, "
        "depth_reached=current depth, gaps=[]), or wrap up (done=true, "
        "depth_reached=final depth, gaps=list of weak points, follow_up=null). "
        "Ask ONE question at a time. Probe for trade-offs and real numbers. "
        "Stop after ~3-5 layers or when you have enough signal."
    )
    return "\n\n".join(parts)


async def run_sage(
    agent: SageAgent,
    memory: MemoryReader,
    *,
    resume: ResumeDocument,
    materials: list[DrillMaterial],
    project: Project | None = None,
    round_: DrillRound = DrillRound.TECH_2,
    direction: str | None = None,
    history: list[dict[str, str]] | None = None,
    answer: str | None = None,
) -> SageVerdict:
    entries = await memory.list_memory(layer="long", limit=8)
    prompt = build_prompt(
        resume=resume,
        materials=materials,
        project=project,
        round_=round_,
        direction=direction,
        history=list(history or []),
        answer=answer,
        memory=entries,
    )
    result = await agent.run(prompt)
    verdict = result.output
    verdict.round = round_.value
    return verdict


def stub_sage(
    *,
    round_: DrillRound,
    project: Project | None,
    answer: str | None,
) -> SageVerdict:
    """No-LLM bypass: opening line on first turn, wrap-up on any answer."""
    if answer is None:
        focus = project.name if project else "简历里的项目"
        if round_ == DrillRound.HR:
            follow = "先简单介绍下你自己，以及为什么想离开现在的公司？"
        else:
            follow = f"先说说你在「{focus}」里具体做了什么？为什么选这套技术栈？"
        return SageVerdict(
            done=False,
            depth_reached=1,
            gaps=[],
            follow_up=follow,
            round=round_.value,
        )
    return SageVerdict(
        done=True,
        depth_reached=2,
        gaps=["stub: 配置 LLM_API_KEY 后由桑迪真追问"],
        follow_up=None,
        round=round_.value,
    )
