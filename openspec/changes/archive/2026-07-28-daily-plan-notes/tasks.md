# Tasks — daily-plan-notes

- [x] OpenSpec proposal / design / tasks
- [x] Core DTOs: PlanItemSource, PlanItemStatus, day/plan/note schemas
- [x] `gotit.db`: ORM models, async session, Alembic migration
- [x] Shared ops: day ensure, plan CRUD, fill-queue, notes, today, ingest_note, examine writeback
- [x] REST routes under `/v1/days`, `/v1/notes`, `/v1/today`, plan item patch
- [x] MCP tools mirroring REST
- [x] Web: date picker, plan list, notes, ingest-from-note
- [x] Tests + `./scripts/gate.sh`
- [x] Update `skills/gotit/SKILL.md`
- [x] Delete ops + routes: plan item, note; GET single note
- [x] Chat persistence: `chat_messages` table + `GET/POST /v1/plan/items/{id}/messages`; Web loads/saves history per item
- [x] Web UI redesign: Apple-style black/white, sidebar workspace, examination chat, compose modal, SVG icon, fixed vite port + proxy

