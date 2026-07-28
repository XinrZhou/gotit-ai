"""Resume structured parsing — Compass (海绵宝宝) extension.

Stage 2 of the two-stage resume parse: plain text -> ResumeDocument.
Reuses the Compass persona (SpongeBob) and the same Pydantic AI wiring.
Falls back to a stub placeholder when no LLM key is configured.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import Agent

from gotit.core.models import ResumeParseOutput

ResumeParserAgent = Agent[Any, ResumeParseOutput]


def build_resume_parser(model: Any, *, system_prompt: str) -> ResumeParserAgent:
    return Agent(
        model,
        output_type=ResumeParseOutput,
        system_prompt=system_prompt,
        name="compass",
    )


def build_prompt(*, resume_text: str) -> str:
    return (
        "## Resume plain text\n"
        f"{resume_text}\n\n"
        "Extract basics + every distinct project into the structured output. "
        "Keep quantified metrics verbatim. One project per entry."
    )


async def run_resume_parser(
    agent: ResumeParserAgent,
    *,
    upload_id: Any,
    resume_text: str,
) -> ResumeParseOutput:
    prompt = build_prompt(resume_text=resume_text)
    result = await agent.run(prompt)
    out = result.output
    # Ensure upload_id is bound on the output (agent returns document only).
    return ResumeParseOutput(upload_id=upload_id, document=out.document)


def stub_parse(*, upload_id: Any, resume_text: str) -> ResumeParseOutput:
    """No-LLM bypass: heuristic rule-based structured parse.

    Delegates to ``heuristic_parse`` (regex + section segmentation) so users
    without an LLM key still get structured basics + projects instead of a
    single placeholder blob. Falls back to a single placeholder project only
    when no structure can be detected at all.
    """
    from gotit.core.resume.heuristic import heuristic_parse

    return heuristic_parse(upload_id=upload_id, resume_text=resume_text)

