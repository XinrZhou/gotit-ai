# Design: state-boundary-tighten

## Architecture (target, incremental)

```text
Web / MCP / Companion(prepare)
        ↓
Interaction (agents: verdict only)
        ↓
Practice close: finalize_examine_with_gate | answer_calibration(source)
        ↓
write_mastery_outcome  ← single mastery row writer
        ↓
Claim + plan (+ digest trigger)
        + trajectory / graph (verify path; calib light trajectory)
```

## P0 — Mastery writer

- `write_mastery_outcome(session, claim_id, verdict, *, source, user_id, prior_failures, follow_up?, reason?)`
  - Internally: current `apply_examine_verdict` body + digest with optional follow_up
  - `apply_examine_verdict` becomes thin alias → `write_mastery_outcome(..., source="verify")` for harness/tests
- `finalize_examine_with_gate` calls writer with `source="verify"` + gate.reason as follow_up seed
- `answer_calibration` calls writer with `source="calibration"`; appends trajectory row with reason=`calibration`
- routes/mcp: no direct import of `apply_examine_verdict` (grep gate in tasks)

## P1 — Practice boundary

- `run_verify_attempt` in `api/`: axiom (or stub) + `finalize_examine_with_gate`; used by chat verify + MCP `gotit_start_verify`
- PracticeKind × Phase documented in SYSTEM (examine|teach|drill|calibration × prepare|closed)
- Companion `start_examine` / `start_verify`: remove claim/plan soft `IN_PROGRESS` writes

## P2 — Memory write model

| Fact | Authority | Memory role |
|------|-----------|-------------|
| mastery / next_review | ClaimRow | none |
| fail structure / confuse | fail_events / graph_edges | trajectory audit |
| failure_digest | derived cache | push + lesson; upsert fill follow_up/reason |
| bootcamp / prefs / note / event | memory OK | product / user |

- `prior_failures`: `count_prior_failures(trajectory)` only; day due fail_count uses same helper (via claim_ids → trajectory counts), not `fail_events` silently

## P3 — Today read model

- PlanItemView: optional `due_reason_code` / `due_reason_text` when claim-linked
- `TodayView.mastery_snapshot`: mastered_count, weak_count, top_due[], recent_fails[]
- `TodayView` lanes: owed | interview | bootcamp already separate fields; document `lane` on focus/bootcamp objects if cheap, else SYSTEM prose
- Companion `get_today` includes due_reason on due_claims (already) + plan reasons when present

## Risks

- Calib trajectory increases prior_failures → schedule intervals; pin with tests (calib almost counts as prior for next verify)
- Digest upsert must not reset `notified`
- Stopping soft IN_PROGRESS may change Brief “almost_today” for prepare-only clicks (intended)
