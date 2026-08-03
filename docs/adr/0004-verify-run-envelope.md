# ADR-0004: Verify Run envelope; gate stays code; chat deferred

- Status: Accepted
- Date: 2026-08-03
- OpenSpec: `openspec/changes/agent-runtime-v2/`

## Context

Gotit already has a hard verify spine: examine/teach agents → Critic →
**`deterministic_gate` (code)** → **`write_mastery_outcome`**. Chat uses a
separate orchestrator with a prepare-only tool whitelist. A full unified
Agent Runtime across chat + verify + ingest would be a large rewrite with high
regression risk and weak Week-1 interview payoff.

VISION P7: the mastery judge is deterministic code, never an LLM. That must
not be weakened while adding “Runtime” vocabulary.

## Decision

1. **Keep** `deterministic_gate` thresholds and schedule formulas unchanged in
   `agent-runtime-v2`. No second judge.
2. Treat **Runtime** as a **thin envelope around the existing verify finalize
   path** (`finalize_examine_with_gate` / shared claim finalize): explicit
   propose → evaluate → commit, with `run_id` / WriteIntent on the audit plane
   when Phase 3 lands.
3. **Do not** rewrite `chat_orchestrator` into the same lifecycle in Phases
   1–3. Chat remains prepare/narrate; mastery close stays on finalize.
4. Ship **Eval Replay + Holdout before** the envelope so behavior is locked
   before structural wrap.
5. LLM outputs must not call `write_mastery_outcome` directly; Commit (finalize
   writer) remains the only verify-path mastery row writer (calibration keeps
   explicit `source=calibration`).

## Alternatives considered

- Big-bang unified RunLifecycle for chat+examine+teach+ingest on day one:
  rejected — cost/risk dominate; chat is not the mastery write path.
- Replacing gate with LLM-as-judge or softer “consensus”: rejected — VISION P7
  / product floor.
- Parallel new finalize service beside `verify_finalize`: rejected — dual-path
  drift; wrap in place instead.

## Consequences

- Week-1 DoD can succeed with Replay + Snapshot + EvidencePack even if Phase 3
  envelope slips.
- Interview framing: production agent ≠ open `while(tool)`; it is a state
  machine with an abort/commit boundary on mastery writes.
- Later chat unification (if ever) needs its own OpenSpec justification and
  must not mount authoritative write tools into companion chat.
- `core` stays framework-free; envelope types live in `gotit.core`, wiring in
  `api/verify_finalize` (and existing shared helpers).
