# Proposal: structure codify

## Why

`db/ops.py` (~1500 lines) and `api/routes.py` (~1240 lines) are single-file
mega-modules spanning every subdomain (day/plan, note, claim, project, resume,
drill, memory, prompt, harness). The web app keeps `api.ts` / `types.ts` /
`store.tsx` / `format.ts` flat at `web/src/` root with no `lib/`, `hooks/`, or
barrel `api/` / `types/` / `store/` packages. Both sides are correct and
working, but the structure does not encode the subdomain boundaries the
product already has, so new code has no home and diffs grow large.

This change splits the two backend mega-modules into subdomain packages and
reorganises the frontend root into purpose-named directories, then codifies
the conventions into Cursor rules so future work follows them.

## What changes

- Backend: `db/ops.py` → `db/ops/` package (`_common`, `day`, `note`, `claim`,
  `project`, `resume`, `drill`, `prompt`, `memory`, `harness`); `api/routes.py`
  → `api/routes/` package (`_common`, `health`, `ingest`, `examine`, `day`,
  `notes`, `teach`, `memory`, `prompts`, `projects`, `resume`, `drill`).
  Both expose a barrel `__init__` so all existing imports
  (`from gotit.db import ops as day_ops`, `from gotit.api.routes import router`)
  stay unchanged — pure internal refactor, zero API/behaviour change.
- Frontend: `web/src/api.ts` → `web/src/api/{client,index}.ts`;
  `types.ts` → `types/index.ts`; `store.tsx` → `store/index.tsx`;
  `format.ts` → `lib/format.ts`; new `hooks/` dir. Barrel `index` files keep
  `from "../api"` / `from "../types"` / `from "../store"` resolving.
- Rules: add `.cursor/rules/backend-structure.mdc` and
  `frontend-structure.mdc` encoding the subdomain layout.

## Out of scope

- No endpoint, schema, DB, or behaviour changes.
- No splitting `mcp/server.py` (kept whole; it is a thin tool surface).
- No new tests; existing tests must pass unchanged (barrel contract).
