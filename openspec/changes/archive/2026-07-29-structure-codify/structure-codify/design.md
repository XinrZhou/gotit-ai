# Design: structure codify

## Backend: `db/ops/` package

Subdomain split (each module owns its rows + views):

| module | responsibility |
|---|---|
| `_common.py` | constants (`DEFAULT_USER_ID`, `EXCERPT_LEN`), shared view helpers (`_excerpt`, `_plan_item_view`, `_note_view`, `_claim_view`) |
| `day.py` | `ensure_day`, plan CRUD, `list_due_claims`, `fill_today_from_queue`, `get_today`, chat messages |
| `note.py` | notes CRUD, `stub_extract_claim`, `_strip_html`, `ingest_note`, `curate_claims`, `list_note_claims`, `list_project_notes` |
| `claim.py` | `apply_examine_result`, `apply_examine_verdict`, `list_topic_claims_today`, `list_project_claims` |
| `project.py` | project CRUD + `project_progress` |
| `resume.py` | resume upsert/get/apply |
| `drill.py` | drill materials + sessions |
| `prompt.py` | prompt register/get/list |
| `memory.py` | memory add/list |
| `harness.py` | harness run/case persistence |

### Circular-import handling

Only one true cycle: `day ↔ note` (`get_today` calls `note.list_notes`;
`note.*` calls `day.ensure_day` / `day.get_plan` / `day.upsert_plan_item`).

Resolution: `day.py` imports `list_notes` from `note.py` at module top
(one direction). `note.py` does **not** import `day` at top level; it uses
**local imports** inside functions (`from gotit.db.ops.day import ensure_day`).
This breaks the cycle at load time. `claim.py` → `day` (local import of
`ensure_day`), `resume.py` → `project`/`note` (top-level, no reverse edge).

### Barrel contract

`db/ops/__init__.py` re-exports every public name (and `_strip_html`, which
`api/routes` reaches via `day_ops._strip_html`) so
`from gotit.db import ops as day_ops` + `day_ops.<name>` is unchanged across
`mcp/server.py`, `api/routes/*`, and `tests/`.

## Backend: `api/routes/` package

Each route module owns `router = APIRouter()` and its Pydantic models.
`routes/__init__.py` builds the aggregate `router` via `include_router` and
exposes it, so `main.py`'s `from gotit.api.routes import router` is unchanged.

Shared helpers live in `routes/_common.py`: `_user_id`, `_resume_ext`,
`_active_prompt`, `_run_sage`, plus resume constants
(`ALLOWED_RESUME_TYPES`, `MAX_RESUME_BYTES`) shared by resume + drill upload.

## Frontend reorg

- `api.ts` (client only: `api`, `uploadFile`, `fetchBlob`) →
  `api/client.ts` + `api/index.ts` barrel.
- `types.ts` → `types/index.ts`.
- `store.tsx` → `store/index.tsx` (internal `./api` → `../api`, `./types` →
  `../types`).
- `format.ts` → `lib/format.ts`; update the 2 call sites
  (`Sidebar`, `NoteComposeModal`) to `../../lib/format`.
- `hooks/` established with `.gitkeep`; convention documented in rule
  (`useStore` stays co-located with its Provider — not moved).

`moduleResolution: bundler` resolves `from "../api"` / `"../types"` /
`"../store"` to the new `*/index.{ts,tsx}`, so component/page imports are
unchanged except `format`.

## Verification

- `uv run ruff check .`, `uv run mypy src`, `uv run pytest` — all green,
  no test edits.
- `cd web && npm run build` (tsc + vite) — green.
- `./scripts/gate.sh` end-to-end.
