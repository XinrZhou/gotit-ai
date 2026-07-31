# Design — MCP verify finalize parity

## Decision

One finalize helper remains the spine: `api/verify_finalize.py` →
`finalize_examine_with_gate`. MCP tools call it inside `session_scope`, same
as REST `_finalize_claim`.

## MCP `gotit_examine`

| Path | Before | After |
|------|--------|-------|
| note/topic session claim-close | `apply_examine_verdict(examine)` | `finalize_examine_with_gate` |
| single + direct `verdict=` | `apply_examine_verdict` | finalize (stub Critic if no key) |
| single + agent `done` | `apply_examine_verdict` | finalize |
| mid-turn (not done) | no writeback | unchanged |

Response gains optional `verify` meta (`examine_verdict` / `recheck_verdict` /
`gate_verdict`) matching REST when a claim closes. Returned `verdict.verdict`
is the **gate** verdict when finalized.

Context: inject `build_budget_subgraph` + failure lessons like REST (MCP was
missing budget block on topic/single paths).

## MCP `gotit_start_verify`

Axiom examine (or provided `examine_verdict`) then
`finalize_examine_with_gate(..., thread_id=...)`. Drop duplicated Critic /
ball / trajectory / mastery block. Gate agent message in thread stays.

## Parity note

REST↔MCP share domain ops + finalize. Direct-verdict bypass is for stubs/tests
only; it still runs Critic (stub echoes) + gate.
