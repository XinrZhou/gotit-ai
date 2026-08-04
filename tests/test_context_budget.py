"""ContextBudget compose / trim priority (no I/O)."""

from __future__ import annotations

from gotit.core.context_budget import ContextBudget, compose_examine_context


def test_both_fit_unchanged() -> None:
    blocks = compose_examine_context(
        "## Prerequisites not yet passed\n- a",
        "## Prior miss lessons\n- tip",
        budget=ContextBudget(graph_max_chars=600, lesson_max_chars=600, total_max_chars=900),
    )
    assert blocks.budget_block is not None
    assert blocks.failure_lesson_block is not None
    assert blocks.trim_signals == []


def test_lesson_dropped_when_total_tight() -> None:
    graph = "G" * 800
    lesson = "## Prior miss lessons\n" + ("L" * 200)
    blocks = compose_examine_context(
        graph,
        lesson,
        budget=ContextBudget(
            graph_max_chars=800, lesson_max_chars=400, total_max_chars=820
        ),
    )
    assert blocks.budget_block is not None
    assert blocks.failure_lesson_block is None
    assert "lesson_dropped_for_total" in blocks.trim_signals


def test_lesson_trimmed_before_graph() -> None:
    graph = "G" * 100
    lesson = "## Prior miss lessons\n" + ("L" * 500)
    blocks = compose_examine_context(
        graph,
        lesson,
        budget=ContextBudget(
            graph_max_chars=200, lesson_max_chars=600, total_max_chars=250
        ),
    )
    assert blocks.budget_block == graph
    assert blocks.failure_lesson_block is not None
    assert len(blocks.failure_lesson_block) <= 250 - 100 - 2
    assert "lesson_trimmed_for_total" in blocks.trim_signals


def test_per_block_clip() -> None:
    graph = "G" * 1000
    blocks = compose_examine_context(
        graph,
        None,
        budget=ContextBudget(graph_max_chars=50, lesson_max_chars=50, total_max_chars=900),
    )
    assert blocks.budget_block is not None
    assert len(blocks.budget_block) == 50
    assert blocks.budget_block.endswith("…")
    assert "graph_clipped" in blocks.trim_signals


def test_empty_inputs() -> None:
    blocks = compose_examine_context(None, None)
    assert blocks.budget_block is None
    assert blocks.failure_lesson_block is None
    assert blocks.trim_signals == []


def test_compile_evidence_pack_hash_stable() -> None:
    from uuid import uuid4

    from gotit.core.context_budget import compile_evidence_pack

    cid = uuid4()
    p1 = compile_evidence_pack(
        recipe="probe",
        claim_id=cid,
        graph_block="## graph\n- a",
        lesson_block="## lessons\n- tip",
        snapshot_fingerprint="abcd1234efgh5678",
        claim_text="claim text",
    )
    p2 = compile_evidence_pack(
        recipe="probe",
        claim_id=cid,
        graph_block="## graph\n- a",
        lesson_block="## lessons\n- tip",
        snapshot_fingerprint="abcd1234efgh5678",
        claim_text="claim text",
    )
    assert p1.pack_hash == p2.pack_hash
    assert p1.budget_block == p2.budget_block
    assert any(b.kind == "claim" for b in p1.blocks)


def test_compile_evidence_pack_trim_signals() -> None:
    from gotit.core.context_budget import ContextBudget, compile_evidence_pack

    pack = compile_evidence_pack(
        recipe="probe",
        claim_id=None,
        graph_block="G" * 800,
        lesson_block="## Prior miss lessons\n" + ("L" * 200),
        budget=ContextBudget(
            graph_max_chars=800, lesson_max_chars=400, total_max_chars=820
        ),
    )
    assert "lesson_dropped_for_total" in pack.trim_signals
    assert pack.failure_lesson_block is None
    assert pack.pack_hash

