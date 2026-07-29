"""Shared helpers and constants for api.routes subdomain modules."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from gotit.api.deps import SessionMemoryReader, SessionPromptReader, get_model
from gotit.api.settings import Settings
from gotit.core.agents.sage import build_sage_agent, run_sage, stub_sage
from gotit.core.models import DrillMaterial, DrillRound, Project, ResumeDocument, SageVerdict
from gotit.db import session_scope

ALLOWED_RESUME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
}
MAX_RESUME_BYTES = 10 * 1024 * 1024


def _user_id(settings: Settings) -> str:
    return settings.gotit_user_id


def _resume_ext(content_type: str) -> str:
    return {
        "application/pdf": "pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "text/plain": "txt",
        "text/markdown": "md",
    }[content_type]


async def _active_prompt(settings: Settings, agent_name: str) -> str:
    async with session_scope() as session:
        prompt = await SessionPromptReader(session).get_active_prompt(agent_name)
        return prompt.system_prompt if prompt else ""


async def _run_sage(
    settings: Settings,
    session: AsyncSession,
    *,
    user_id: str,
    resume: ResumeDocument,
    materials: list[DrillMaterial],
    project: Project | None,
    round_: DrillRound,
    direction: str | None,
    answer: str | None,
) -> SageVerdict:
    if not settings.llm_api_key:
        return stub_sage(round_=round_, project=project, answer=answer)
    system_prompt = await SessionPromptReader(session).get_active_prompt("sage")
    system_prompt_text = system_prompt.system_prompt if system_prompt else ""
    reader = SessionMemoryReader(session, user_id=user_id)
    agent = build_sage_agent(get_model(), system_prompt=system_prompt_text)
    return await run_sage(
        agent,
        reader,
        resume=resume,
        materials=materials,
        project=project,
        round_=round_,
        direction=direction,
        answer=answer,
    )
