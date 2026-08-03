# Tasks: state-boundary-tighten

## OpenSpec

- [x] proposal / design / tasks landed

## P0 — Mastery writer

- [x] `write_mastery_outcome` in `db/ops/claim.py`; wire digest follow_up/reason
- [x] `finalize_examine_with_gate` + `answer_calibration` use writer; calib append trajectory
- [x] Deprecate note on `apply_examine_result`; export writer from barrel
- [x] Grep: no `apply_examine_verdict` in `api/routes` / `mcp/tools`
- [x] Tests: calibration + verify finalize + schedule (+ digest upsert)

## P1 — Practice

- [x] `run_verify_attempt` shared by chat + MCP start_verify
- [x] Stop companion soft IN_PROGRESS
- [x] SYSTEM: PracticeKind × Phase + prepare vs execute

## P2 — Memory

- [x] `maybe_record_failure_digest` upsert fill empty follow_up/reason; keep notified
- [x] Day due fail_count from trajectory prior helper (single source)
- [x] SYSTEM: memory write model table

## P3 — Today

- [x] Plan items get due_reason when claim-linked
- [x] `MasterySnapshot` on TodayView
- [x] Companion get_today aligns key fields; Web types if needed
- [x] Minimal Brief / types consume (no loud UI)

## Verify

- [x] Relevant pytest + five-question review note in SYSTEM

## Follow-up debt (post-acceptance P1/P2)

- [x] Remove `apply_examine_result` stub; tests use `write_mastery_outcome`
- [x] Clarify fail count: schedule/Brief = owe_next; graph = `fail_event_count`
- [x] Share `finalize_claim_by_id` for REST examine/teach + MCP
