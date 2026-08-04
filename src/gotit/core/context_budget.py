"""Unified examine-context budget + EvidencePack compiler (VISION P4).

Graph block (depends / confuse / fail) and failure-lesson block each have
per-block caps; ``compose_examine_context`` / ``compile_evidence_pack`` enforce
a combined ``total_max`` so the two never silently stack past the examiner
budget.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

EvidenceRecipe = Literal["probe", "teach_back", "chat_light"]


@dataclass(frozen=True)
class ContextBudget:
    """Caps for re-examine prompt sections."""

    graph_max_chars: int = 600
    lesson_max_chars: int = 600
    total_max_chars: int = 900


DEFAULT_CONTEXT_BUDGET = ContextBudget()


@dataclass(frozen=True)
class ContextBlocks:
    """Composed blocks ready for Axiom ``build_prompt``."""

    budget_block: str | None
    failure_lesson_block: str | None
    trim_signals: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EvidenceBlock:
    """One budgeted context chunk (post-trim text)."""

    kind: str  # claim | confuse | lesson | plan | source | history
    text: str
    priority: int
    chars: int


@dataclass(frozen=True)
class EvidencePack:
    """Compiled, hashable context for one verify LLM call.

    ``budget_block`` / ``failure_lesson_block`` mirror ``ContextBlocks`` for
    existing axiom/echo call sites.
    """

    recipe: EvidenceRecipe
    claim_id: UUID | None
    blocks: tuple[EvidenceBlock, ...]
    budget: ContextBudget
    trim_signals: tuple[str, ...]
    pack_hash: str
    budget_block: str | None
    failure_lesson_block: str | None
    snapshot_fingerprint: str | None = None


def _clip(text: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    if max_chars == 1:
        return "…"
    return text[: max_chars - 1] + "…"


def compose_examine_context(
    budget_block: str | None,
    failure_lesson_block: str | None,
    *,
    budget: ContextBudget = DEFAULT_CONTEXT_BUDGET,
) -> ContextBlocks:
    """Apply per-block then total char budget.

    When over ``total_max_chars``, drop/trim **lessons first**, then truncate
    the graph block. Never invent content — only shrink or omit.
    """
    signals: list[str] = []
    graph = (budget_block or "").strip() or None
    lesson = (failure_lesson_block or "").strip() or None

    if graph and len(graph) > budget.graph_max_chars:
        graph = _clip(graph, budget.graph_max_chars)
        signals.append("graph_clipped")
    if lesson and len(lesson) > budget.lesson_max_chars:
        lesson = _clip(lesson, budget.lesson_max_chars)
        signals.append("lesson_clipped")

    g_len = len(graph) if graph else 0
    l_len = len(lesson) if lesson else 0
    total = g_len + l_len
    # +2 for the blank line join cost when both present
    join = 2 if graph and lesson else 0
    if total + join <= budget.total_max_chars:
        return ContextBlocks(
            budget_block=graph,
            failure_lesson_block=lesson,
            trim_signals=signals,
        )

    # Prefer keeping graph; shrink or drop lessons.
    room_for_lesson = budget.total_max_chars - g_len - (2 if graph else 0)
    if lesson and room_for_lesson < 40:
        signals.append("lesson_dropped_for_total")
        lesson = None
        l_len = 0
        join = 0
    elif lesson and l_len > room_for_lesson:
        lesson = _clip(lesson, max(0, room_for_lesson))
        signals.append("lesson_trimmed_for_total")
        l_len = len(lesson)
        join = 2 if graph and lesson else 0

    total = (len(graph) if graph else 0) + (len(lesson) if lesson else 0) + join
    if total > budget.total_max_chars and graph:
        keep = budget.total_max_chars - (len(lesson) if lesson else 0)
        if lesson:
            keep -= 2
        if keep < 40:
            signals.append("graph_dropped_for_total")
            graph = None
        else:
            graph = _clip(graph, keep)
            signals.append("graph_trimmed_for_total")

    return ContextBlocks(
        budget_block=graph,
        failure_lesson_block=lesson,
        trim_signals=signals,
    )


def evidence_pack_hash(
    *,
    recipe: str,
    claim_id: UUID | None,
    budget_block: str | None,
    failure_lesson_block: str | None,
    trim_signals: list[str] | tuple[str, ...],
    snapshot_fingerprint: str | None = None,
) -> str:
    """Deterministic pack id for replay / audit (not cryptographic secrecy)."""
    parts = [
        recipe,
        str(claim_id) if claim_id else "",
        budget_block or "",
        failure_lesson_block or "",
        "|".join(trim_signals),
        snapshot_fingerprint or "",
    ]
    raw = "\n".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def compile_evidence_pack(
    *,
    recipe: EvidenceRecipe,
    claim_id: UUID | None,
    graph_block: str | None,
    lesson_block: str | None,
    budget: ContextBudget = DEFAULT_CONTEXT_BUDGET,
    snapshot_fingerprint: str | None = None,
    claim_text: str | None = None,
) -> EvidencePack:
    """Compile graph + lesson (+ optional claim) into a hashable EvidencePack.

    Trim policy delegates to ``compose_examine_context`` (lessons before graph).
    """
    # teach_back: still budget lessons; graph optional (may be None).
    composed = compose_examine_context(graph_block, lesson_block, budget=budget)
    blocks: list[EvidenceBlock] = []
    if claim_text and claim_text.strip():
        text = claim_text.strip()
        blocks.append(
            EvidenceBlock(kind="claim", text=text, priority=0, chars=len(text))
        )
    if composed.budget_block:
        blocks.append(
            EvidenceBlock(
                kind="confuse",
                text=composed.budget_block,
                priority=1,
                chars=len(composed.budget_block),
            )
        )
    if composed.failure_lesson_block:
        blocks.append(
            EvidenceBlock(
                kind="lesson",
                text=composed.failure_lesson_block,
                priority=2,
                chars=len(composed.failure_lesson_block),
            )
        )
    signals = tuple(composed.trim_signals)
    digest = evidence_pack_hash(
        recipe=recipe,
        claim_id=claim_id,
        budget_block=composed.budget_block,
        failure_lesson_block=composed.failure_lesson_block,
        trim_signals=signals,
        snapshot_fingerprint=snapshot_fingerprint,
    )
    return EvidencePack(
        recipe=recipe,
        claim_id=claim_id,
        blocks=tuple(blocks),
        budget=budget,
        trim_signals=signals,
        pack_hash=digest,
        budget_block=composed.budget_block,
        failure_lesson_block=composed.failure_lesson_block,
        snapshot_fingerprint=snapshot_fingerprint,
    )


# Back-compat alias used in design docs / OpenSpec wording.
build_evidence_pack = compile_evidence_pack
