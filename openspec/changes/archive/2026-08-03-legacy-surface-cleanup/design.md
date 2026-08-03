# Design: legacy-surface-cleanup

## chat_messages

Created historically for plan-item examiner/echo turns; companion-arch moved
history to `messages`. Examine/teach pass client `history` and optionally
`workflow_persist` into threads. No skill or frontend hits
`/v1/plan/items/{id}/messages`.

Drop via alembic (Postgres) + remove model so `create_all` / SQLite no longer
recreates it. 7 local rows in `gotit.db` are abandoned — dropped with table.

## VerifyLoop

Never wired by routes. Live path: `VerifyWorkflow` over `BallCustody` +
`deterministic_gate` + `finalize_examine_with_gate`. Delete class; keep
`LoopState` (still used by ingest stub response).

## Redis

No imports of `redis` package; remove dep, compose service, settings field.
