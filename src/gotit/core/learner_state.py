"""Derived learner state projection (ADR-0003) — framework-free.

``LearnerStateSnapshot`` is a **read model**, not an authoritative table.
Assemble from claim / plan / fail / graph / digest inputs; never patch the
snapshot as if it were source-of-truth mastery state.

Async DB loading lives in ``gotit.db.ops.learner_state.build_learner_state``.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class OwedSummary(BaseModel):
    """Due ∪ plan-open style owed rollup (counts + samples)."""

    due_count: int = 0
    due_reason_counts: dict[str, int] = Field(default_factory=dict)
    sample_claim_ids: list[UUID] = Field(default_factory=list)


class WeakCluster(BaseModel):
    topic: str | None = None
    claim_ids: list[UUID] = Field(default_factory=list)
    severity: int = 0


class ConfusionEdge(BaseModel):
    a: UUID
    b: UUID
    rel: Literal["confused_with"] = "confused_with"
    weight: int = 1


class FailureLessonView(BaseModel):
    claim_id: UUID | None = None
    excerpt: str = ""
    verdict: str | None = None
    topic: str | None = None
    updated_at: str | None = None


class LearnerPrefsView(BaseModel):
    """Light product prefs — not mastery authority."""

    bootcamp_lane: str | None = None
    interview_lane: str | None = None
    digest_enabled: bool | None = None


class LearnerStateSnapshot(BaseModel):
    """Derived projection of long-term learner state for agents / eval."""

    as_of: date
    user_id: str
    owed_summary: OwedSummary = Field(default_factory=OwedSummary)
    weak_clusters: list[WeakCluster] = Field(default_factory=list)
    active_confusions: list[ConfusionEdge] = Field(default_factory=list)
    failure_lessons: list[FailureLessonView] = Field(default_factory=list)
    interview_lane: str | None = None
    prefs: LearnerPrefsView = Field(default_factory=LearnerPrefsView)
    context_fingerprint: str = ""


def compute_context_fingerprint(
    *,
    as_of: date,
    owed_claim_ids: list[UUID],
    lesson_claim_ids: list[UUID | None],
    confusion_pairs: list[tuple[UUID, UUID, int]],
    interview_lane: str | None = None,
) -> str:
    """Stable short hash for eval replay / pack association."""
    payload = {
        "as_of": as_of.isoformat(),
        "owed": sorted(str(x) for x in owed_claim_ids),
        "lessons": sorted(str(x) for x in lesson_claim_ids if x is not None),
        "confusions": sorted(
            [f"{a}:{b}:{w}" for a, b, w in confusion_pairs]
        ),
        "lane": interview_lane or "",
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def assemble_learner_state(
    *,
    as_of: date,
    user_id: str,
    owed_summary: OwedSummary,
    weak_clusters: list[WeakCluster],
    active_confusions: list[ConfusionEdge],
    failure_lessons: list[FailureLessonView],
    interview_lane: str | None = None,
    prefs: LearnerPrefsView | None = None,
    context_fingerprint: str | None = None,
) -> LearnerStateSnapshot:
    """Pure assembler — callers supply already-loaded authoritative reads."""
    prefs_v = prefs or LearnerPrefsView()
    lane = interview_lane if interview_lane is not None else prefs_v.interview_lane
    fp = context_fingerprint or compute_context_fingerprint(
        as_of=as_of,
        owed_claim_ids=list(owed_summary.sample_claim_ids),
        lesson_claim_ids=[x.claim_id for x in failure_lessons],
        confusion_pairs=[(e.a, e.b, e.weight) for e in active_confusions],
        interview_lane=lane,
    )
    return LearnerStateSnapshot(
        as_of=as_of,
        user_id=user_id,
        owed_summary=owed_summary,
        weak_clusters=weak_clusters,
        active_confusions=active_confusions,
        failure_lessons=failure_lessons,
        interview_lane=lane,
        prefs=prefs_v,
        context_fingerprint=fp,
    )


def snapshot_to_debug_dict(snapshot: LearnerStateSnapshot) -> dict[str, Any]:
    """Compact dict for harness traces (not prompt dump)."""
    return {
        "as_of": snapshot.as_of.isoformat(),
        "user_id": snapshot.user_id,
        "fingerprint": snapshot.context_fingerprint,
        "due_count": snapshot.owed_summary.due_count,
        "weak_clusters": len(snapshot.weak_clusters),
        "confusions": len(snapshot.active_confusions),
        "lessons": len(snapshot.failure_lessons),
        "interview_lane": snapshot.interview_lane,
    }


__all__ = [
    "ConfusionEdge",
    "FailureLessonView",
    "LearnerPrefsView",
    "LearnerStateSnapshot",
    "OwedSummary",
    "WeakCluster",
    "assemble_learner_state",
    "compute_context_fingerprint",
    "snapshot_to_debug_dict",
]
