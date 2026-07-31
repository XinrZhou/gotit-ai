"""Chat message ``metadata.action_blocks`` helpers.

Structured, tappable cards for owed claims and verify outcomes. Cap keeps
bubbles quiet; payloads stay id + short labels (no full note bodies).
"""

from __future__ import annotations

from typing import Any

ACTION_BLOCKS_CAP = 5

_FAIL_VERDICTS = frozenset({"almost", "owe_next"})


def clip_title(text: str, limit: int = 80) -> str:
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    return t[: max(0, limit - 1)] + "…"


def owed_claim_block(
    *,
    claim_id: str,
    title: str,
    due_reason_text: str | None = None,
) -> dict[str, object]:
    block: dict[str, object] = {
        "type": "owed_claim",
        "claim_id": str(claim_id),
        "title": clip_title(title),
        "actions": [{"id": "start_examine", "label": "开考"}],
    }
    if due_reason_text:
        block["due_reason_text"] = due_reason_text
    return block


def owed_blocks_from_claims(
    claims: list[Any], *, limit: int = ACTION_BLOCKS_CAP
) -> list[dict[str, object]]:
    """Build owed_claim blocks from Claim-like objects (id / text / due_reason_text)."""
    out: list[dict[str, object]] = []
    for c in claims[:limit]:
        cid = getattr(c, "id", None)
        if cid is None and isinstance(c, dict):
            cid = c.get("id")
        text = getattr(c, "text", None)
        if text is None and isinstance(c, dict):
            text = c.get("text") or c.get("title")
        reason = getattr(c, "due_reason_text", None)
        if reason is None and isinstance(c, dict):
            reason = c.get("due_reason_text")
        if cid is None or not text:
            continue
        out.append(
            owed_claim_block(
                claim_id=str(cid),
                title=str(text),
                due_reason_text=str(reason) if reason else None,
            )
        )
    return out


def verdict_block(
    *,
    gate_verdict: str,
    claim_id: str | None = None,
) -> dict[str, object]:
    block: dict[str, object] = {
        "type": "verdict",
        "gate_verdict": gate_verdict,
        "actions": [],
    }
    if claim_id:
        block["claim_id"] = str(claim_id)
        if gate_verdict in _FAIL_VERDICTS:
            block["actions"] = [{"id": "start_examine", "label": "再练"}]
    return block


def attach_verdict_blocks(
    meta: dict[str, object],
    *,
    gate_verdict: str | None,
    claim_id: Any = None,
) -> dict[str, object]:
    """Add a capped verdict action_block when gate closed a claim."""
    if not gate_verdict:
        return meta
    cid = str(claim_id) if claim_id is not None else None
    meta["action_blocks"] = [verdict_block(gate_verdict=gate_verdict, claim_id=cid)]
    return meta


def collect_action_blocks(
    tool_calls: list[dict[str, object]] | None,
    *,
    limit: int = ACTION_BLOCKS_CAP,
) -> list[dict[str, object]]:
    """Merge ``action_blocks`` from successful tool trail entries (capped)."""
    if not tool_calls:
        return []
    out: list[dict[str, object]] = []
    for call in tool_calls:
        if not call.get("ok"):
            continue
        raw = call.get("action_blocks")
        if not isinstance(raw, list):
            continue
        for item in raw:
            if isinstance(item, dict) and item.get("type"):
                out.append(item)
                if len(out) >= limit:
                    return out
    return out
