from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from gotit.api.deps import (
    SessionMemoryReader,
    SessionPromptReader,
    get_model,
)
from gotit.api.settings import Settings, get_settings
from gotit.api.workflow_persist import (
    drill_agent_text,
)
from gotit.core.agents.sage import build_sage_agent, run_sage, stub_sage
from gotit.core.models import (
    DrillMaterial,
    DrillRound,
    Project,
    ResumeDocument,
    SageVerdict,
)
from gotit.db import ops as day_ops
from gotit.db import session_scope
from gotit.db.runtime import ensure_db
from gotit.mcp.app import mcp
from gotit.mcp.common import (
    _user_id,
)


@mcp.tool()
async def gotit_list_drill_materials() -> list[dict[str, object]]:
    """List all deep-dive materials for the user."""
    await ensure_db()
    async with session_scope() as session:
        mats = await day_ops.list_drill_materials(session, user_id=_user_id())
    return [m.model_dump(mode="json") for m in mats]

@mcp.tool()
async def gotit_upsert_drill_material(
    title: str,
    body: str,
    material_id: str | None = None,
) -> dict[str, object]:
    """Create or update a deep-dive material (pass id to update)."""
    await ensure_db()
    async with session_scope() as session:
        m = await day_ops.upsert_drill_material(
            session,
            material_id=UUID(material_id) if material_id else None,
            title=title,
            body=body,
            user_id=_user_id(),
        )
    return m.model_dump(mode="json")

@mcp.tool()
async def gotit_delete_drill_material(material_id: str) -> dict[str, str]:
    """Delete a deep-dive material by id."""
    await ensure_db()
    async with session_scope() as session:
        await day_ops.delete_drill_material(session, UUID(material_id), user_id=_user_id())
    return {"status": "deleted"}

@mcp.tool()
async def gotit_list_drill_sessions() -> list[dict[str, object]]:
    """List all mock-interview drill sessions (newest first)."""
    await ensure_db()
    async with session_scope() as session:
        sessions = await day_ops.list_drill_sessions(session, user_id=_user_id())
    return [s.model_dump(mode="json") for s in sessions]

@mcp.tool()
async def gotit_get_drill_session(session_id: str) -> dict[str, object]:
    """Get a single drill session (with messages)."""
    await ensure_db()
    async with session_scope() as session:
        s = await day_ops.get_drill_session(session, UUID(session_id), user_id=_user_id())
    return s.model_dump(mode="json")

@mcp.tool()
async def gotit_start_drill_session(
    round: str,
    direction: str | None = None,
    project_id: str | None = None,
    thread_id: str | None = None,
) -> dict[str, object]:
    """Start a resume-driven mock interview session. `round` is tech_1/2/3/4/hr.
    Optional `thread_id` appends turns to the companion thread stream."""
    await ensure_db()
    settings = get_settings()
    user_id = _user_id()
    tid = UUID(thread_id) if thread_id else None
    async with session_scope() as session:
        resume = await day_ops.get_resume(session, user_id=user_id)
        if resume is None:
            raise ValueError("no resume imported yet; upload a resume first")
        round_ = DrillRound(round)
        project: Project | None = None
        if project_id:
            project = await day_ops.get_project(session, UUID(project_id), user_id=user_id)
        materials = await day_ops.list_drill_materials(session, user_id=user_id)
        ds = await day_ops.create_drill_session(
            session,
            resume_id=resume.id,
            round_=round_,
            direction=direction,
            project_id=UUID(project_id) if project_id else None,
            user_id=user_id,
        )
        verdict = await _mcp_run_sage(
            settings, session,
            user_id=user_id,
            resume=resume.document,
            materials=materials,
            project=project,
            round_=round_,
            direction=direction,
            answer=None,
        )
        await day_ops.append_drill_message(
            session, ds.id, role="examiner", text=verdict.follow_up or "", user_id=user_id
        )
        if verdict.done:
            await day_ops.finish_drill_session(session, ds.id, user_id=user_id)
        if tid is not None:
            await day_ops.append_workflow_exchange(
                session,
                thread_id=tid,
                user_id=user_id,
                workflow="drill",
                agent_name="sage",
                agent_text=drill_agent_text(
                    done=verdict.done,
                    depth_reached=verdict.depth_reached,
                    gaps=list(verdict.gaps),
                    follow_up=verdict.follow_up,
                ),
                user_text=None,
                extra_metadata={
                    "drill_session_id": str(ds.id),
                    "session_done": verdict.done,
                },
            )
    return {"session": ds.model_dump(mode="json"), "verdict": verdict.model_dump(mode="json")}

@mcp.tool()
async def gotit_continue_drill_session(
    session_id: str,
    answer: str,
    thread_id: str | None = None,
) -> dict[str, object]:
    """Continue a drill session with the candidate's latest answer.
    Optional `thread_id` appends turns to the companion thread stream."""
    await ensure_db()
    settings = get_settings()
    user_id = _user_id()
    tid = UUID(thread_id) if thread_id else None
    async with session_scope() as session:
        ds = await day_ops.get_drill_session(session, UUID(session_id), user_id=user_id)
        if ds.status == "done":
            raise ValueError("session already done")
        resume = await day_ops.get_resume(session, user_id=user_id)
        if resume is None:
            raise ValueError("no resume")
        project: Project | None = None
        if ds.project_id:
            try:
                project = await day_ops.get_project(session, ds.project_id, user_id=user_id)
            except KeyError:
                project = None
        materials = await day_ops.list_drill_materials(session, user_id=user_id)
        await day_ops.append_drill_message(
            session, ds.id, role="user", text=answer, user_id=user_id
        )
        verdict = await _mcp_run_sage(
            settings, session,
            user_id=user_id,
            resume=resume.document,
            materials=materials,
            project=project,
            round_=ds.round,
            direction=ds.direction,
            answer=answer,
        )
        await day_ops.append_drill_message(
            session, ds.id, role="examiner", text=verdict.follow_up or "", user_id=user_id
        )
        if verdict.done:
            await day_ops.finish_drill_session(session, ds.id, user_id=user_id)
        if tid is not None:
            await day_ops.append_workflow_exchange(
                session,
                thread_id=tid,
                user_id=user_id,
                workflow="drill",
                agent_name="sage",
                agent_text=drill_agent_text(
                    done=verdict.done,
                    depth_reached=verdict.depth_reached,
                    gaps=list(verdict.gaps),
                    follow_up=verdict.follow_up,
                ),
                user_text=answer,
                extra_metadata={
                    "drill_session_id": str(ds.id),
                    "session_done": verdict.done,
                },
            )
    return {"verdict": verdict.model_dump(mode="json")}


# --- helpers ---


async def _mcp_run_sage(
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

