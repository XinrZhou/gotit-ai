# Tasks: structure codify

## Backend

- [x] Create `src/gotit/db/ops/` package: `_common`, `day`, `note`, `claim`,
      `project`, `resume`, `drill`, `prompt`, `memory`, `harness`, `__init__`
      (barrel re-exporting all public names + `_strip_html`).
- [x] Delete `src/gotit/db/ops.py`.
- [x] Create `src/gotit/api/routes/` package: `_common`, `health`, `ingest`,
      `examine`, `day`, `notes`, `teach`, `memory`, `prompts`, `projects`,
      `resume`, `drill`, `__init__` (aggregate `router`).
- [x] Delete `src/gotit/api/routes.py`.
- [x] `uv run ruff check .` green.
- [x] `uv run mypy src` green.
- [x] `uv run pytest` green (no test edits; fixed pre-existing date-drift in
      `test_apply_resume_clear_rebuild` to query today's day).

## Frontend

- [x] `web/src/api.ts` → `api/client.ts` + `api/index.ts` barrel.
- [x] `web/src/types.ts` → `types/index.ts`.
- [x] `web/src/store.tsx` → `store/index.tsx` (fix internal imports).
- [x] `web/src/format.ts` → `lib/format.ts`; update `Sidebar`, `NoteComposeModal`.
- [x] Add `web/src/hooks/.gitkeep`.
- [x] `cd web && npm run build` green.

## Codify

- [x] Add `.cursor/rules/backend-structure.mdc`.
- [x] Add `.cursor/rules/frontend-structure.mdc`.

## Gate

- [x] `./scripts/gate.sh` green (ruff + mypy + 29 pytest + harness pass).

## Closeout

- [x] Sync OpenSpec artifacts to final code; archive to
      `openspec/changes/archive/2026-07-29-structure-codify/`.
