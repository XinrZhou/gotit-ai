# Proposal: legacy-surface-cleanup

## Why

Follow-up to `mcp-split-stack-honest`. Dead surfaces still in tree: plan-item
`chat_messages` (no Web/MCP/test callers), in-memory `VerifyLoop` skeleton,
and unused Redis dependency/settings.

## What changes

1. Drop `chat_messages` table + ORM/ops/`GET|POST /v1/plan/items/{id}/messages`
   + `ChatMessageView` (companion uses `threads`/`messages` only).
2. Remove `VerifyLoop`; keep `VerifyWorkflow` + `deterministic_gate`; retarget
   `tests/test_loop.py`.
3. Remove Redis from `pyproject` / Compose / `Settings.redis_url`.

## Out

- APPLY verify workflow
- Making drill claim-close share examine finalize
- Multi-tenant auth

## Impact

- alembic `0015_drop_chat_messages`
- `docs/SYSTEM.md` stack/layout note
