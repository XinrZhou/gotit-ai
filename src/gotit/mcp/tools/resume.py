from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from gotit.api.deps import (
    get_model,
)
from gotit.api.settings import get_settings
from gotit.core.models import (
    ResumeDocument,
)
from gotit.core.resume.extract import extract_text
from gotit.core.resume.parse import (
    build_resume_parser,
    load_resume_system_prompt,
    run_resume_parser,
    stub_parse,
)
from gotit.db import ops as day_ops
from gotit.db import session_scope
from gotit.db.runtime import ensure_db
from gotit.mcp.app import mcp
from gotit.mcp.common import (
    _user_id,
)


def _resume_content_type(path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    return {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "txt": "text/plain",
        "md": "text/markdown",
    }.get(ext, "text/plain")


def _resume_ext(content_type: str) -> str:
    return {
        "application/pdf": "pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "text/plain": "txt",
        "text/markdown": "md",
    }[content_type]


@mcp.tool()
async def gotit_upload_resume(file_path: str) -> dict[str, object]:
    """Upload a resume file (local path), extract text + parse to ResumeDocument.

    MCP stdio cannot pass multipart; OpenClaw downloads the file and passes a
    local path. Returns {upload_id, file_path, document}.
    """
    await ensure_db()
    settings = get_settings()
    path = Path(file_path)
    content = path.read_bytes()
    if len(content) > 10 * 1024 * 1024:
        raise ValueError("resume file too large (max 10MB)")
    content_type = _resume_content_type(path)
    upload_id = uuid4()
    ext = _resume_ext(content_type)
    stored = f"uploads/{upload_id}.{ext}"
    Path(stored).parent.mkdir(parents=True, exist_ok=True)
    Path(stored).write_bytes(content)
    resume_text = extract_text(content, content_type)
    if not settings.llm_api_key:
        out = stub_parse(upload_id=upload_id, resume_text=resume_text)
    else:
        system_prompt = load_resume_system_prompt()
        agent = build_resume_parser(get_model(), system_prompt=system_prompt)
        out = await run_resume_parser(agent, upload_id=upload_id, resume_text=resume_text)
    return {
        "upload_id": str(upload_id),
        "file_path": stored,
        "document": out.document.model_dump(mode="json"),
    }

@mcp.tool()
async def gotit_apply_resume(
    upload_id: str,
    document: dict[str, object],
    ingest: bool = False,
    file_path: str | None = None,
) -> dict[str, object]:
    """Apply an (edited) parsed resume: clear-rebuild projects (no quiz notes)."""
    await ensure_db()
    doc = ResumeDocument.model_validate(document)
    resolved = file_path
    if not resolved or not Path(resolved).exists():
        candidates = sorted(Path("uploads").glob(f"{upload_id}.*"))
        if candidates:
            resolved = str(candidates[0])
        elif file_path:
            resolved = file_path
        else:
            resolved = f"uploads/{upload_id}"
    async with session_scope() as session:
        return await day_ops.apply_resume(
            session,
            doc,
            upload_id=UUID(upload_id),
            file_path=resolved,
            ingest=ingest,
            user_id=_user_id(),
        )

@mcp.tool()
async def gotit_get_resume() -> dict[str, object] | None:
    """Return the current global resume record (or null if none)."""
    await ensure_db()
    async with session_scope() as session:
        rec = await day_ops.get_resume(session, user_id=_user_id())
    return rec.model_dump(mode="json") if rec else None

