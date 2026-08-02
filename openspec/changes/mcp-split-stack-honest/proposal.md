# Proposal: mcp-split-stack-honest

## Why

Personal / single-user companion (no multi-tenant). Stack narrative drifted from
code: Redis is in Compose/docs but unused; `VerifyLoop` reads like the live
state machine though production closes via `VerifyWorkflow` +
`finalize_examine_with_gate`; MCP tools live in one ~2k-line `server.py`.

## What changes

1. Split `mcp/server.py` into subdomain `mcp/tools/*` (same tool names /
   signatures; still thin → `db.ops` / shared finalize / chat orchestrator).
2. Honest stack docs: Postgres (or SQLite) is the data plane; Redis optional /
   unused today; deploy posture = single `GOTIT_USER_ID` + API key.
3. Document the real verify spine vs legacy `VerifyLoop`; note dual message
   tables (`messages` for companion threads vs legacy plan-item
   `chat_messages`).

## Out

- Multi-tenant auth / per-user isolation
- Wiring Redis for real use
- Deleting `VerifyLoop` or migrating off `chat_messages` (document only)
- Tool behavior / schema changes

## Impact

- `src/gotit/mcp/` layout; `gotit-mcp` entry unchanged
- `docs/SYSTEM.md`, README pair, `.env.example` comments
- Tests that `from gotit.mcp.server import gotit_*` keep working via re-export
