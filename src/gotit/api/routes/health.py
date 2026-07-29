"""Health probe."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from gotit import __version__

router = APIRouter()


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(version=__version__)
