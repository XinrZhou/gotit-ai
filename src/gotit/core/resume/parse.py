"""Resume structured parsing — Compass (海绵宝宝) extension.

Stage 2 of the two-stage resume parse: plain text -> ResumeDocument.
Uses ``prompts/resume.md`` (not the active compass claim-curation prompt).
Falls back to a heuristic stub when no LLM key is configured.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic_ai import Agent

from gotit.core.models import ResumeDocument, ResumeParseOutput
from gotit.prompts import load_prompt_file

ResumeParserAgent = Agent[Any, ResumeDocument]

# ~12k chars ≈ enough for a long CN resume; head+tail keeps early/late projects.
MAX_RESUME_CHARS = 12_000

_RESUME_PROMPT_PATH = Path(__file__).resolve().parents[4] / "prompts" / "resume.md"


def load_resume_system_prompt() -> str:
    """System prompt for resume structured parse (file-backed)."""
    if not _RESUME_PROMPT_PATH.is_file():
        return (
            "Extract basics + every distinct project into ResumeDocument. "
            "Keep quantified metrics verbatim. One project per entry."
        )
    return load_prompt_file(_RESUME_PROMPT_PATH).system_prompt


def clip_resume_text(text: str, *, max_chars: int = MAX_RESUME_CHARS) -> str:
    """Truncate overlong resume text for the LLM, keeping head and tail."""
    text = text.strip()
    if len(text) <= max_chars:
        return text
    marker = "\n\n…[中间已截断，保留首尾]…\n\n"
    budget = max_chars - len(marker)
    head = (budget * 2) // 3
    tail = budget - head
    return text[:head] + marker + text[-tail:]


def build_resume_parser(model: Any, *, system_prompt: str) -> ResumeParserAgent:
    return Agent(
        model,
        output_type=ResumeDocument,
        system_prompt=system_prompt,
        name="resume",
    )


def build_prompt(*, resume_text: str) -> str:
    clipped = clip_resume_text(resume_text)
    return (
        "## Resume plain text\n"
        f"{clipped}\n\n"
        "Extract basics + every distinct project into the structured output. "
        "Keep quantified metrics verbatim. One project per entry."
    )


async def run_resume_parser(
    agent: ResumeParserAgent,
    *,
    upload_id: UUID | Any,
    resume_text: str,
) -> ResumeParseOutput:
    prompt = build_prompt(resume_text=resume_text)
    result = await agent.run(prompt)
    return ResumeParseOutput(upload_id=upload_id, document=result.output)


def stub_parse(*, upload_id: Any, resume_text: str) -> ResumeParseOutput:
    """No-LLM bypass: heuristic rule-based structured parse.

    Delegates to ``heuristic_parse`` (regex + section segmentation) so users
    without an LLM key still get structured basics + projects instead of a
    single placeholder blob. Falls back to a single placeholder project only
    when no structure can be detected at all.
    """
    from gotit.core.resume.heuristic import heuristic_parse

    return heuristic_parse(upload_id=upload_id, resume_text=resume_text)
