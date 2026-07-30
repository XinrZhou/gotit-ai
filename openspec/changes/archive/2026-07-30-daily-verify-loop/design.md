# daily-verify-loop — design

## Trust path (shared)

Extract finalize used by `/v1/threads/{id}/verify` and `/v1/examine` when a
claim closes:

```
examine_verdict (Axiom)
  → Critic recheck (identity / CRITIC_* / stub)
  → deterministic_gate (stricter-of-two)
  → apply_examine_verdict(gate)
  → append_trajectory + mastery-graph writeback
```

Response / message metadata:

| field | meaning |
|-------|---------|
| `verdict` / `gate_verdict` | mastery outcome shown to learner |
| `examine_verdict` | Axiom alone |
| `recheck_verdict` | Critic |
| `gate.reason` | human-readable gate line |

UI reads structured fields only — no bubble parse.

## Today brief

- Data: existing `GET /v1/today` → `due_claims` + `plan.items` (workspace
  already loads plan; add due_claims).
- Surfaces: no-thread empty, empty active thread, Examine picker head.
- 开考: `note_id` if note has claims; else `claim_id` conversational examine.

## Personal scope guardrails

- No vector RAG; due list stays mastery / SR queue.
- Trajectory UI is a quiet step row, not an ops dashboard.
