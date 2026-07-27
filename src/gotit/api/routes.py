from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from gotit import __version__
from gotit.api.auth import require_api_key
from gotit.core.models import CheckMode, Claim, LoopState

router = APIRouter()


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str


class IngestRequest(BaseModel):
    material: str = Field(min_length=1, description="Raw study material to extract claims from")


class IngestResponse(BaseModel):
    claims: list[Claim]
    state: LoopState
    note: str = "stub: claim extraction not wired yet"


class ExamineRequest(BaseModel):
    claim_id: str
    mode: CheckMode = CheckMode.PROBE


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(version=__version__)


@router.post("/v1/ingest", response_model=IngestResponse, dependencies=[Depends(require_api_key)])
async def ingest(body: IngestRequest) -> IngestResponse:
    # Stub: real Librarian extraction lands in a later change.
    claim = Claim(text=body.material.strip()[:500], source_excerpt=body.material[:200])
    return IngestResponse(claims=[claim], state=LoopState.CLAIM)


@router.post("/v1/examine", dependencies=[Depends(require_api_key)])
async def examine(body: ExamineRequest) -> dict[str, object]:
    return {
        "claim_id": body.claim_id,
        "mode": body.mode,
        "status": "stub",
        "message": "Examiner not wired yet",
    }
