# Design: agent-runtime-v2

## North star (engineering, not product)

```text
Surfaces (Web / MCP) — unchanged UX contract
        ↓
Verify path (examine | teach | thread-verify)
        ↓
EvidencePack ← LearnerStateSnapshot (derived read)
        ↓
Execute (Axiom / Echo / Critic) → proposed verdicts only
        ↓
Evaluate: deterministic_gate (+ VerifyWorkflow ball)
        ↓
Commit: write_mastery_outcome (+ trajectory / graph as today)
        ↓
Eval: Replay + Holdout lock the above
```

Chat companion stays a **separate** prepare/narrate surface until a later
change explicitly unifies it. Phase 1–3 do **not** rewrite
`chat_orchestrator`.

## Architecture decisions

### A. LearnerStateSnapshot is derived-only (ADR-0003)

- Pydantic (or dataclass) in `gotit.core`; builder reads claims / plan /
  fail_events / graph_edges / failure_digest.
- **No** new authoritative table for “learner profile.”
- Prompt / Brief / Replay fixtures should converge on the same builder over
  time; Phase 2 **requires** verify Pack + unit tests on the builder.
- `memory_entries` remain non-mastery (prefs / trajectory audit / digest cache).

### B. EvidencePack extends ContextBudget (no parallel budget system)

- Today: `compose_examine_context` + duplicated callers in
  `verify_attempt` / examine / teach / MCP.
- Target: `build_evidence_pack(snapshot, claim_id, recipe, budget) →
  EvidencePack` with blocks, `trim_signals`, `pack_hash`.
- Trim policy **inherits** current behavior: per-block caps; on total overflow
  shrink/drop lessons before graph (VISION P4).
- Phase 2 success = all verify LLM context entry points call Pack; chat may
  keep existing assembly.

### C. Verify Run envelope is a thin wrap (ADR-0004)

- Do **not** invent a second finalize path.
- Wrap `finalize_examine_with_gate`: Intent/Plan (routing) → Execute (agents)
  → Evaluate (gate) → Commit (`write_mastery_outcome`).
- LLM output may only enter `proposed_*` / WriteIntent; Commit is the only
  mastery writer on the verify path.
- `run_id` on audit/trajectory metadata; idempotent commit key when envelope
  lands (Phase 3).
- `deterministic_gate` thresholds and `schedule_after_verdict` formulas are
  **frozen** in this change.

### D. Evaluation: Replay + Holdout (Phase 1 first)

- Keep existing `dev` / `gold` contract rollups
  (`gate_consistent`, `no_spurious_write`, …).
- Add `holdout` case_set **isolated** from gold (VISION P5).
- Add `scripts/run_replay_harness.py`: stub / fixture path → assert gate +
  writeback contracts **without** live LLM.
- Wire into `scripts/gate.sh`.
- Human `adopt|observe|reject` stays audit-only; bind `suite_version`.

## Module map (allowed touch list)

| Module | Role in this change |
|--------|---------------------|
| `core/loop.py` | **Read/call only** — no threshold edits |
| `db/ops/claim.write_mastery_outcome` | **Call only** — no verdict semantics change |
| `core/context_budget.py` | Extend → Pack compiler |
| `core/learner_state.py` (new) | Snapshot + builder |
| `core/agent_run.py` (new, Phase 3) | Thin types + wrap helpers |
| `api/verify_finalize.py` | Thin envelope (Phase 3) |
| `api/verify_attempt.py`, examine/teach routes + MCP | Pack consumers (Phase 2) |
| `harness/*`, `scripts/run_*` | Replay / holdout (Phase 1) |
| `api/chat_orchestrator.py` | **Do not rewrite** (Phase 1–3) |
| `web/**` | **Out** |

## Risks

| Risk | Mitigation |
|------|------------|
| Big-bang Runtime rewrite | Phase order: Eval → Snapshot/Pack → optional envelope |
| Snapshot becomes second truth | ADR-0003; no authoritative learner table |
| Replay flakes on copy | Assert contracts (gate/write/pack_hash), not prose |
| Scope bleed into UX OpenSpecs | Proposal Out; no web commits in this change |
| Pack trim silently changes prompts | Replay `pack_hash_stable` / trim_signal cases before caller migration |

## Diagrams

### WritePlane

```text
AUTHORITATIVE  claim mastery, next_review, plan status, fail_events, graph_edges
DERIVED        failure_digest, LearnerStateSnapshot, Brief owed aggregates
AUDIT          trajectory, harness decisions, run_id / WriteIntent / pack_hash
EPHEMERAL      run working memory, proposed writes, LLM scratch
```

### Phase dependency

```text
Phase 0 Spec/ADR
    → Phase 1 Replay+Holdout (lock behavior)
        → Phase 2 Snapshot+EvidencePack (verify callers)
            → Phase 3 Run envelope (optional)
                → Phase 4 ToolSpec+Trace (later; not Week-1 DoD)
```
