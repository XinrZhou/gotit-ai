# Design — daily-plan-notes

## Approach

手写笔记使用社区封装的语雀 Lake 编辑器 `yuque-editor-core`（非官方，源自语雀浏览器插件同源能力）：

- Vite 插件 `yuqueAssets()` 在 dev/build 时拷贝离线静态资源到 `public/yuque-assets`
- 业务侧只依赖薄封装 `web/src/components/YuqueNoteEditor.tsx`（读写 HTML / lake、字数、空文档判断）
- 存库默认 `text/html`；链接导入与压缩包导入为后续迭代

其余 REST/MCP/计划队列设计不变。

## REST ↔ MCP parity

| REST | MCP |
|------|-----|
| `GET /v1/days/{date}/plan` | `gotit_get_plan` |
| `POST /v1/days/{date}/plan/items` | `gotit_upsert_plan_item` |
| `POST /v1/days/{date}/plan/fill-queue` | `gotit_fill_today_from_queue` |
| `PATCH /v1/plan/items/{id}` | `gotit_update_plan_item` |
| `GET/POST /v1/days/{date}/notes` | `gotit_list_notes` / `gotit_add_note` |
| `POST /v1/notes/{id}/ingest` | `gotit_ingest_note` |
| `GET /v1/today` | `gotit_today` |

## Risks

- No Docker locally → tests use `sqlite+aiosqlite` when `GOTIT_TEST_DATABASE_URL` unset; production path remains Postgres.
- Examine remains stub; writeback uses request flag `passed` for deterministic tests until real Examiner lands.
