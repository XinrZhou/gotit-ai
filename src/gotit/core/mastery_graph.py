"""Mastery-graph constants and pure budget helpers (framework-free)."""

from __future__ import annotations

from uuid import UUID

CONFUSED_THRESHOLD = 2
BUDGET_CONFUSED_MAX = 2
BUDGET_FAIL_REASONS_MAX = 3
FAIL_VERDICTS = frozenset({"almost", "owe_next"})


def canonical_claim_pair(a: UUID, b: UUID) -> tuple[UUID, UUID]:
    """Undirected edge endpoints with stable order."""
    return (a, b) if str(a) <= str(b) else (b, a)


def pick_confused_neighbors(
    *,
    target_id: UUID,
    edges: list[tuple[UUID, UUID, int]],
    limit: int = BUDGET_CONFUSED_MAX,
    threshold: int = CONFUSED_THRESHOLD,
) -> list[UUID]:
    """Pick highest-weight active confused neighbors for ``target_id``.

    ``edges`` items are ``(source, target, weight)`` with canonical ordering.
    """
    scored: list[tuple[int, UUID]] = []
    for src, tgt, weight in edges:
        if weight < threshold:
            continue
        if src == target_id:
            scored.append((weight, tgt))
        elif tgt == target_id:
            scored.append((weight, src))
    scored.sort(key=lambda x: (-x[0], str(x[1])))
    return [cid for _, cid in scored[:limit]]


def format_budget_block(
    *,
    confused_labels: list[str],
    fail_reasons: list[str],
    max_chars: int = 600,
) -> str | None:
    """Prompt section for Axiom; None when empty. Caps total size near failure-lesson budget."""
    parts: list[str] = []
    if confused_labels:
        lines = "\n".join(f"- {t}" for t in confused_labels)
        parts.append(f"## Easy to confuse with\n{lines}")
    if fail_reasons:
        lines = "\n".join(f"- {r}" for r in fail_reasons[:BUDGET_FAIL_REASONS_MAX])
        parts.append(f"## Recent failures on this claim\n{lines}")
    if not parts:
        return None
    block = "\n\n".join(parts)
    if len(block) > max_chars:
        return block[: max_chars - 1] + "…"
    return block
