"""REST routes for cold-start calibration."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from gotit.api.auth import require_api_key
from gotit.api.routes._common import _user_id
from gotit.api.settings import Settings, get_settings
from gotit.core.models import CalibrationSessionView, SyntheticCalibrationResult
from gotit.db import ops as day_ops
from gotit.db import session_scope

router = APIRouter()


class CalibrationStartIn(BaseModel):
    note_id: UUID | None = None
    topic: str | None = Field(default=None, max_length=200)
    claim_ids: list[UUID] | None = None
    as_of: date | None = None


class CalibrationAnswerIn(BaseModel):
    claim_id: UUID
    outcome: Literal["correct", "incorrect"]
    as_of: date | None = None


class SyntheticCalibrationIn(BaseModel):
    true_theta: float = Field(ge=0.5, le=5.5)
    note_id: UUID | None = None
    topic: str | None = Field(default=None, max_length=200)
    claim_ids: list[UUID] | None = None
    mode: Literal["deterministic", "bernoulli_threshold"] = "deterministic"
    as_of: date | None = None


@router.post(
    "/v1/calibration/start",
    response_model=CalibrationSessionView,
    dependencies=[Depends(require_api_key)],
)
async def calibration_start(
    body: CalibrationStartIn,
    settings: Annotated[Settings, Depends(get_settings)],
) -> CalibrationSessionView:
    async with session_scope() as session:
        try:
            return await day_ops.start_calibration(
                session,
                user_id=_user_id(settings),
                note_id=body.note_id,
                topic=body.topic,
                claim_ids=body.claim_ids,
                as_of=body.as_of,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc


@router.get(
    "/v1/calibration/{session_id}",
    response_model=CalibrationSessionView,
    dependencies=[Depends(require_api_key)],
)
async def calibration_get(
    session_id: UUID,
    settings: Annotated[Settings, Depends(get_settings)],
) -> CalibrationSessionView:
    async with session_scope() as session:
        try:
            return await day_ops.get_calibration(
                session, session_id, user_id=_user_id(settings)
            )
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc


@router.post(
    "/v1/calibration/{session_id}/answer",
    response_model=CalibrationSessionView,
    dependencies=[Depends(require_api_key)],
)
async def calibration_answer(
    session_id: UUID,
    body: CalibrationAnswerIn,
    settings: Annotated[Settings, Depends(get_settings)],
) -> CalibrationSessionView:
    async with session_scope() as session:
        try:
            return await day_ops.answer_calibration(
                session,
                session_id,
                claim_id=body.claim_id,
                outcome=body.outcome,
                user_id=_user_id(settings),
                as_of=body.as_of,
            )
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc


@router.post(
    "/v1/calibration/synthetic",
    response_model=SyntheticCalibrationResult,
    dependencies=[Depends(require_api_key)],
)
async def calibration_synthetic(
    body: SyntheticCalibrationIn,
    settings: Annotated[Settings, Depends(get_settings)],
) -> SyntheticCalibrationResult:
    async with session_scope() as session:
        try:
            return await day_ops.run_synthetic_calibration(
                session,
                true_theta=body.true_theta,
                note_id=body.note_id,
                topic=body.topic,
                claim_ids=body.claim_ids,
                user_id=_user_id(settings),
                mode=body.mode,
                as_of=body.as_of,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc
