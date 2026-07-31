# MCP verify finalize parity

## Why

REST `/v1/examine` and thread verify already share `finalize_examine_with_gate`
(Critic → deterministic gate → trajectory / mastery writeback). MCP
`gotit_examine` still called `apply_examine_verdict` with the examiner's raw
verdict, and `gotit_start_verify` inlined a duplicate Critic+gate path.
That breaks REST↔MCP parity and the product iron law: mastery must not be
LLM self-judgment alone.

## What changes

- Route MCP examine claim-close (session / single / direct verdict) through
  the same `finalize_examine_with_gate` helper as REST.
- Route `gotit_start_verify` through the same helper after Axiom examine.
- Align MCP examine context injection with REST (budget subgraph + failure
  lessons) for single-claim and topic/note sessions.
- Tests covering MCP direct-verdict gate path; OpenSpec + SYSTEM sync.

## Out

- Teach / drill full Critic+gate (mastery writeback stays on examine spine).
- Moving `verify_finalize` into `gotit.core` (stays API-layer orchestration).
