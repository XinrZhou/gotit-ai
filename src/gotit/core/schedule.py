"""Deterministic spaced-review schedule (framework-free; no LLM).

Simplified SM-2 / FSRS-inspired interval table — not a full Anki/FSRS port.

## Formula (pinned by tests)

Given ``as_of`` (local learning day) and ``prior_failures`` (count of prior
non-passed verifies on this claim, before the current attempt):

| verdict   | next_review_at                         | reason_code     |
|-----------|----------------------------------------|-----------------|
| passed    | ``None`` (cleared)                     | passed_clear    |
| almost    | ``as_of`` (+0d, still due today)       | almost_today    |
| owe_next  | ``as_of + min(MAX, 1 + 2×prior_fails)``| owe_scheduled   |

``MAX_INTERVAL_DAYS = 30`` caps runaway queues after many fails.

## Due sort key

``(-overdue_days, depends_blocked, -severity, -confuse_weight, id)`` —
earlier in the list = more urgent. Claims with unmet ``depends_on`` prereqs
are demoted (``depends_blocked=1``) so unlocked / prereq work can surface first.
``severity`` is fail-event count; ``confuse_weight`` is max ``confused_with``
edge weight touching the claim (0 if none).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal
from uuid import UUID

ScheduleReasonCode = Literal["passed_clear", "almost_today", "owe_scheduled"]
DueReasonCode = Literal[
    "overdue",
    "almost_today",
    "owe_scheduled",
    "confuse_boost",
    "depends",
    "queued",
]

MAX_INTERVAL_DAYS = 30
# Missing next_review_at → treat as long-overdue so it sorts ahead of fresh dues.
_NULL_OVERDUE_DAYS = 10_000


@dataclass(frozen=True)
class ScheduleResult:
    """Pure scheduling outcome — persistence layer writes ``next_review_at``."""

    next_review_at: date | None
    reason_code: ScheduleReasonCode
    interval_days: int | None = None


def owe_interval_days(prior_failures: int) -> int:
    """Days until next review after ``owe_next``: ``min(30, 1 + 2×prior_failures)``."""
    raw = 1 + 2 * max(int(prior_failures), 0)
    return min(MAX_INTERVAL_DAYS, raw)


def compute_next_review(
    verdict: str,
    *,
    as_of: date,
    prior_failures: int = 0,
) -> ScheduleResult:
    """Map gate verdict → next review date + reason (deterministic)."""
    if verdict == "passed":
        return ScheduleResult(next_review_at=None, reason_code="passed_clear")
    if verdict == "almost":
        # Still due today (+0). Do not push to tomorrow.
        return ScheduleResult(
            next_review_at=as_of,
            reason_code="almost_today",
            interval_days=0,
        )
    if verdict == "owe_next":
        interval = owe_interval_days(prior_failures)
        return ScheduleResult(
            next_review_at=as_of + timedelta(days=interval),
            reason_code="owe_scheduled",
            interval_days=interval,
        )
    raise ValueError(f"unknown verdict: {verdict}")


def schedule_after_verdict(
    verdict: str,
    *,
    prior_failures: int = 0,
    as_of: date | None = None,
) -> ScheduleResult:
    """Writeback / gate entry point — same formula as ``compute_next_review``."""
    return compute_next_review(
        verdict,
        as_of=as_of or date.today(),
        prior_failures=prior_failures,
    )


def overdue_days(*, as_of: date, next_review_at: date | None) -> int:
    """How many days past due; ``None`` review date counts as heavily overdue."""
    if next_review_at is None:
        return _NULL_OVERDUE_DAYS
    return max(0, (as_of - next_review_at).days)


def due_sort_key(
    *,
    as_of: date,
    next_review_at: date | None,
    fail_count: int = 0,
    confuse_weight: int = 0,
    depends_blocked: bool = False,
    claim_id: UUID | str,
) -> tuple[int, int, int, int, str]:
    """Sort key for due lists / fill-from-queue (ascending = highest priority).

    ``fail_count`` here means trajectory ``owe_next`` priors (SR weighting),
    not ``fail_events`` / graph ``fail_event_count``.
    """
    return (
        -overdue_days(as_of=as_of, next_review_at=next_review_at),
        1 if depends_blocked else 0,
        -max(int(fail_count), 0),
        -max(int(confuse_weight), 0),
        str(claim_id),
    )


def max_confuse_weight_for_claim(
    claim_id: UUID,
    edges: list[tuple[UUID, UUID, int]],
) -> int:
    """Max ``confused_with`` weight on edges touching ``claim_id`` (0 if none)."""
    best = 0
    for src, tgt, weight in edges:
        if src == claim_id or tgt == claim_id:
            best = max(best, int(weight))
    return best


def confuse_weights_from_edges(
    claim_ids: list[UUID],
    edges: list[tuple[UUID, UUID, int]],
) -> dict[UUID, int]:
    """Map each claim id → max confuse edge weight (missing → 0)."""
    out = {cid: 0 for cid in claim_ids}
    for src, tgt, weight in edges:
        w = int(weight)
        if src in out:
            out[src] = max(out[src], w)
        if tgt in out:
            out[tgt] = max(out[tgt], w)
    return out


def top_confuse_neighbor_ids(
    *,
    target_id: UUID,
    edges: list[tuple[UUID, UUID, int]],
    limit: int = 1,
    min_weight: int = 1,
) -> list[UUID]:
    """Highest-weight confuse neighbors for due-reason labels / re-practice hints."""
    scored: list[tuple[int, UUID]] = []
    for src, tgt, weight in edges:
        if int(weight) < min_weight:
            continue
        if src == target_id:
            scored.append((int(weight), tgt))
        elif tgt == target_id:
            scored.append((int(weight), src))
    scored.sort(key=lambda x: (-x[0], str(x[1])))
    return [cid for _, cid in scored[: max(0, limit)]]


def unmet_depends_prereq_ids(
    *,
    claim_id: UUID,
    depends_edges: list[tuple[UUID, UUID]],
    mastered_ids: set[UUID],
) -> list[UUID]:
    """Directed ``depends_on``: ``(dependent, prereq)``; return unmet prereqs.

    Stable order by prereq id string. Empty when all prereqs are mastered.
    """
    unmet = [
        pre
        for dep, pre in depends_edges
        if dep == claim_id and pre not in mastered_ids
    ]
    unmet.sort(key=str)
    return unmet


def depends_blocked_map(
    claim_ids: list[UUID],
    *,
    depends_edges: list[tuple[UUID, UUID]],
    mastered_ids: set[UUID],
) -> dict[UUID, bool]:
    """True when the claim has at least one unmet ``depends_on`` prereq."""
    return {
        cid: bool(
            unmet_depends_prereq_ids(
                claim_id=cid,
                depends_edges=depends_edges,
                mastered_ids=mastered_ids,
            )
        )
        for cid in claim_ids
    }


_DUE_REASON_TEXT: dict[DueReasonCode, str] = {
    "almost_today": "上次还差点，今天接着",
    "overdue": "已过建议复习日",
    "owe_scheduled": "按计划该复习",
    "confuse_boost": "易与邻近点搞混",
    "depends": "前置尚未过关",
    "queued": "还在队列里，轮到了",
}


def _with_fail_hint(text: str, fail_count: int) -> str:
    if fail_count <= 0:
        return text
    return f"{text}（曾挂过 {fail_count} 次）"


def explain_due_reason(
    *,
    as_of: date,
    status: str,
    next_review_at: date | None,
    confuse_weight: int = 0,
    confuse_threshold: int = 2,
    confuse_neighbor_label: str | None = None,
    depends_prereq_label: str | None = None,
    fail_count: int = 0,
) -> tuple[DueReasonCode, str]:
    """Human-facing due reason for today views (server-assembled; UI does not parse formula).

    ``fail_count`` = trajectory ``owe_next`` count (Brief「曾挂过」); not graph
    ``fail_event_count`` (almost|owe_next event rows).
    """
    status_l = (status or "").lower()
    fails = max(int(fail_count), 0)
    if status_l == "in_progress":
        return "almost_today", _with_fail_hint(_DUE_REASON_TEXT["almost_today"], fails)
    if depends_prereq_label:
        label = depends_prereq_label.strip()[:40]
        return "depends", f"前置「{label}」尚未过关"
    if next_review_at is not None and next_review_at < as_of:
        days = (as_of - next_review_at).days
        base = f"已过建议复习日 {days} 天"
        return "overdue", _with_fail_hint(base, fails)
    if confuse_weight >= confuse_threshold and confuse_neighbor_label:
        label = confuse_neighbor_label.strip()[:40]
        return "confuse_boost", f"易与「{label}」搞混"
    if confuse_weight >= confuse_threshold:
        return "confuse_boost", _DUE_REASON_TEXT["confuse_boost"]
    if next_review_at is not None and next_review_at <= as_of:
        return "owe_scheduled", _with_fail_hint(
            _DUE_REASON_TEXT["owe_scheduled"], fails
        )
    if next_review_at is None:
        return "queued", _with_fail_hint(_DUE_REASON_TEXT["queued"], fails)
    return "owe_scheduled", _DUE_REASON_TEXT["owe_scheduled"]


# Naming aliases (parallel Agent / older drafts).
due_priority_key = due_sort_key
confuse_weight_by_claim = max_confuse_weight_for_claim
explain_due = explain_due_reason
