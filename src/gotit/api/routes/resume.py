"""Resume upload / parse / apply / fetch endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from gotit.api.auth import require_api_key
from gotit.api.deps import get_model
from gotit.api.routes._common import (
    ALLOWED_RESUME_TYPES,
    MAX_RESUME_BYTES,
    _active_prompt,
    _resume_ext,
    _user_id,
)
from gotit.api.settings import Settings, get_settings
from gotit.core.models import ResumeDocument, ResumeRecord
from gotit.core.resume.extract import ResumeExtractError, extract_text
from gotit.core.resume.parse import build_resume_parser, run_resume_parser, stub_parse
from gotit.db import ops as day_ops
from gotit.db import session_scope

router = APIRouter()


class ResumeApplyRequest(BaseModel):
    upload_id: UUID
    document: ResumeDocument
    file_path: str
    ingest: bool = False


_RESUME_MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
}


@router.post(
    "/v1/resumes/upload",
    dependencies=[Depends(require_api_key)],
)
async def upload_resume(
    file: Annotated[UploadFile, Field(alias="file")],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    content = await file.read()
    if len(content) > MAX_RESUME_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="resume file too large (max 10MB)",
        )
    content_type = (file.content_type or "text/plain").strip()
    if content_type not in ALLOWED_RESUME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"unsupported content type: {content_type}",
        )
    upload_id = uuid4()
    ext = _resume_ext(content_type)
    file_path = f"uploads/{upload_id}.{ext}"
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    Path(file_path).write_bytes(content)
    try:
        resume_text = extract_text(content, content_type)
    except ResumeExtractError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    if not settings.llm_api_key:
        out = stub_parse(upload_id=upload_id, resume_text=resume_text)
        return {
            "upload_id": str(upload_id),
            "file_path": file_path,
            "document": out.document.model_dump(mode="json"),
        }

    system_prompt = await _active_prompt(settings, "compass")
    agent = build_resume_parser(get_model(), system_prompt=system_prompt)
    out = await run_resume_parser(agent, upload_id=upload_id, resume_text=resume_text)
    return {
        "upload_id": str(upload_id),
        "file_path": file_path,
        "document": out.document.model_dump(mode="json"),
    }


@router.post(
    "/v1/resumes/apply",
    dependencies=[Depends(require_api_key)],
)
async def apply_resume(
    body: ResumeApplyRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    async with session_scope() as session:
        result = await day_ops.apply_resume(
            session,
            body.document,
            upload_id=body.upload_id,
            file_path=body.file_path,
            ingest=body.ingest,
            user_id=_user_id(settings),
        )
    return result


@router.get(
    "/v1/resumes",
    response_model=ResumeRecord | None,
    dependencies=[Depends(require_api_key)],
)
async def get_resume(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ResumeRecord | None:
    async with session_scope() as session:
        return await day_ops.get_resume(session, user_id=_user_id(settings))


@router.get(
    "/v1/resumes/file",
    dependencies=[Depends(require_api_key)],
)
async def get_resume_file(
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    """Serve the originally uploaded resume file (pdf/docx/txt/md)."""
    async with session_scope() as session:
        record = await day_ops.get_resume(session, user_id=_user_id(settings))
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no resume")
    file_path = record.file_path
    # Fallback for legacy rows whose file_path lacked an extension: glob by upload_id.
    if not Path(file_path).exists():
        candidates = sorted(Path("uploads").glob(f"{record.upload_id}.*"))
        if candidates:
            file_path = str(candidates[0])
    if not Path(file_path).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="resume file missing on disk"
        )
    ext = Path(file_path).suffix.lstrip(".").lower()
    media_type = _RESUME_MEDIA_TYPES.get(ext, "application/octet-stream")
    return FileResponse(file_path, media_type=media_type, filename=f"resume.{ext or 'bin'}")
