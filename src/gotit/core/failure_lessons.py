"""Budgeted failure_digest → Axiom examine context (P4; framework-free)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

# Hard caps — keep examiner context small (VISION P4).
FAILURE_LESSON_MAX_ITEMS = 3
FAILURE_LESSON_MAX_CHARS = 600
FAILURE_LESSON_LINE_MAX = 160
FAILURE_LESSON_FETCH_LIMIT = 40


@dataclass(frozen=True)
class FailureLessonCandidate:
    """One failure_digest row, flattened for ranking / formatting."""

    claim_id: str
    verdict: str
    claim_text: str
    follow_up: str | None
    topic: str | None
    created_at: datetime


def _priority(
    candidate: FailureLessonCandidate,
    *,
    claim_id: UUID,
    neighbor_ids: set[str],
    topic: str | None,
) -> int | None:
    """0 = same claim, 1 = confuse neighbor, 2 = same topic; None = skip."""
    cid = candidate.claim_id
    if cid == str(claim_id):
        return 0
    if cid in neighbor_ids:
        return 1
    if topic and candidate.topic and candidate.topic == topic:
        return 2
    return None


def select_failure_lessons(
    candidates: list[FailureLessonCandidate],
    *,
    claim_id: UUID,
    neighbor_ids: list[UUID] | set[UUID] | None = None,
    topic: str | None = None,
    max_items: int = FAILURE_LESSON_MAX_ITEMS,
) -> list[FailureLessonCandidate]:
    """Rank digests: same claim → confuse neighbors → same topic; newest first."""
    neighbors = {str(n) for n in (neighbor_ids or [])}
    ranked: list[tuple[int, datetime, FailureLessonCandidate]] = []
    seen_keys: set[tuple[str, str]] = set()
    for c in candidates:
        if not c.claim_id or c.verdict not in {"almost", "owe_next"}:
            continue
        prio = _priority(c, claim_id=claim_id, neighbor_ids=neighbors, topic=topic)
        if prio is None:
            continue
        key = (c.claim_id, c.verdict)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        ranked.append((prio, c.created_at, c))
    ranked.sort(key=lambda t: (t[0], -t[1].timestamp()))
    return [c for _, _, c in ranked[: max(0, max_items)]]


def _line_for(
    candidate: FailureLessonCandidate,
    *,
    current_claim_id: str,
    line_max: int = FAILURE_LESSON_LINE_MAX,
) -> str:
    tip = (candidate.follow_up or "").strip() or (candidate.claim_text or "").strip()
    tip = tip[:line_max]
    if candidate.claim_id == current_claim_id:
        return f"- [{candidate.verdict}] {tip}"
    claim_snip = (candidate.claim_text or "").strip()[:80]
    if tip and claim_snip and tip != claim_snip:
        body = f"{claim_snip} — {tip}"
    else:
        body = claim_snip or tip
    return f"- [{candidate.verdict}] {body[:line_max]}"


def brief_failure_hint(
    *,
    follow_up: str | None,
    claim_text: str | None = None,
    max_chars: int = 72,
) -> str | None:
    """One quiet DailyBrief line from a failure_digest tip."""
    tip = (follow_up or "").strip() or (claim_text or "").strip()
    if not tip:
        return None
    if len(tip) > max_chars:
        tip = tip[: max_chars - 1] + "…"
    return f"曾栽过：{tip}"


def learner_failure_hint(block: str | None, *, max_chars: int = 120) -> str | None:
    """Quiet one-liner for the learner UI from an examiner lesson block."""
    if not block or not block.strip():
        return None
    lines = [
        ln.strip().lstrip("- ").strip()
        for ln in block.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    # Drop the Chinese header line if present as a bare sentence.
    lines = [ln for ln in lines if not ln.startswith("你曾在这些点栽过")]
    if not lines:
        return None
    tip = lines[0]
    # Strip leading [almost] / [owe_next] tags for a calmer learner line.
    if tip.startswith("[") and "]" in tip:
        tip = tip.split("]", 1)[1].strip()
    tip = tip.strip()
    if not tip:
        return None
    if len(tip) > max_chars:
        tip = tip[: max_chars - 1] + "…"
    return f"你曾在这栽过：{tip}"


def format_failure_lesson_block(
    lessons: list[FailureLessonCandidate],
    *,
    claim_id: UUID,
    max_chars: int = FAILURE_LESSON_MAX_CHARS,
) -> str | None:
    """Short '你曾在这些点栽过' list for Axiom; None when empty / over-truncated to empty."""
    if not lessons:
        return None
    header = "## Prior miss lessons\n你曾在这些点栽过："
    lines: list[str] = []
    used = len(header)
    current = str(claim_id)
    for lesson in lessons:
        line = _line_for(lesson, current_claim_id=current)
        # +1 for newline between header/lines
        cost = len(line) + 1
        if used + cost > max_chars:
            break
        lines.append(line)
        used += cost
    if not lines:
        return None
    return header + "\n" + "\n".join(lines)


def budget_failure_lesson_block(
    candidates: list[FailureLessonCandidate],
    *,
    claim_id: UUID,
    neighbor_ids: list[UUID] | set[UUID] | None = None,
    topic: str | None = None,
    max_items: int = FAILURE_LESSON_MAX_ITEMS,
    max_chars: int = FAILURE_LESSON_MAX_CHARS,
) -> str | None:
    """Select + format in one call (pure; no I/O)."""
    selected = select_failure_lessons(
        candidates,
        claim_id=claim_id,
        neighbor_ids=neighbor_ids,
        topic=topic,
        max_items=max_items,
    )
    return format_failure_lesson_block(
        selected, claim_id=claim_id, max_chars=max_chars
    )
