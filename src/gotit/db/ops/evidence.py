"""Load + compile EvidencePack for verify LLM entry points."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from gotit.core.context_budget import (
    DEFAULT_CONTEXT_BUDGET,
    ContextBudget,
    EvidencePack,
    EvidenceRecipe,
    compile_evidence_pack,
)
from gotit.core.learner_state import LearnerStateSnapshot
from gotit.db.ops._common import DEFAULT_USER_ID
from gotit.db.ops.graph import build_budget_subgraph
from gotit.db.ops.learner_state import build_learner_state
from gotit.db.ops.memory import build_failure_lesson_block

VerifyRecipe = Literal["probe", "teach_back"]


async def build_evidence_pack_for_claim(
    session: AsyncSession,
    *,
    claim_id: UUID,
    user_id: str = DEFAULT_USER_ID,
    topic: str | None = None,
    recipe: VerifyRecipe = "probe",
    claim_text: str | None = None,
    neighbor_claim_ids: list[UUID] | None = None,
    budget: ContextBudget = DEFAULT_CONTEXT_BUDGET,
    snapshot: LearnerStateSnapshot | None = None,
    include_snapshot: bool = True,
) -> EvidencePack:
    """Single entry for examine/teach/verify: subgraph + lessons → EvidencePack.

    Does not write mastery. Callers must pass Pack fields into agents — do not
    hand-roll ``compose_examine_context`` beside this helper.
    """
    recipe_t: EvidenceRecipe = recipe
    graph_block: str | None = None
    neighbors = list(neighbor_claim_ids or [])
    if recipe_t == "probe":
        budget_view = await build_budget_subgraph(
            session, user_id=user_id, claim_id=claim_id
        )
        graph_block = budget_view.prompt_block
        for nid in budget_view.confused_claim_ids:
            if nid not in neighbors:
                neighbors.append(nid)

    lesson_block = await build_failure_lesson_block(
        session,
        user_id=user_id,
        claim_id=claim_id,
        topic=topic,
        neighbor_claim_ids=neighbors or None,
    )

    snap_fp: str | None = None
    if snapshot is not None:
        snap_fp = snapshot.context_fingerprint
    elif include_snapshot:
        snap = await build_learner_state(session, user_id=user_id)
        snap_fp = snap.context_fingerprint

    return compile_evidence_pack(
        recipe=recipe_t,
        claim_id=claim_id,
        graph_block=graph_block,
        lesson_block=lesson_block,
        budget=budget,
        snapshot_fingerprint=snap_fp,
        claim_text=claim_text,
    )
