"""Aggregate FastAPI router for gotit-ai.

Each subdomain lives in its own module; this package exposes a single
``router`` so ``main.py`` keeps ``from gotit.api.routes import router``.
"""

from __future__ import annotations

from fastapi import APIRouter

from gotit.api.routes import (
    bootcamp,
    calibration,
    chat,
    claims,
    connectors,
    day,
    drill,
    examine,
    health,
    identities,
    ingest,
    interviews,
    memory,
    notes,
    projects,
    prompts,
    resume,
    shell,
    skills,
    teach,
)

router = APIRouter()
router.include_router(health.router)
router.include_router(chat.router)
router.include_router(identities.router)
router.include_router(skills.router)
router.include_router(connectors.router)
router.include_router(ingest.router)
router.include_router(examine.router)
router.include_router(calibration.router)
router.include_router(bootcamp.router)
router.include_router(day.router)
router.include_router(notes.router)
router.include_router(claims.router)
router.include_router(teach.router)
router.include_router(memory.router)
router.include_router(shell.router)
router.include_router(prompts.router)
router.include_router(projects.router)
router.include_router(resume.router)
router.include_router(drill.router)
router.include_router(interviews.router)

__all__ = ["router"]
