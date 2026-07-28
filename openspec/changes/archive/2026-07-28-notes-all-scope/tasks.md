# Tasks — notes-all-scope

## 后端
- [x] 1. `DayNoteView` 加 `day: date`；`_note_view` 从 learning_day 填充
- [x] 2. `db/ops.list_all_notes(user_id)` 跨天列笔记（带 day）
- [x] 3. `GET /v1/notes` 路由 + MCP `gotit_list_all_notes`
- [x] 3b. `list_note_claims` 改按 note.claim_ids 顺序（抽取顺序）

## 前端
- [x] 4. store：`noteScope` + `allNotes`；scope=all 时 refresh 拉 `/v1/notes`；`notes` 按 scope 切换
- [x] 5. 侧栏「今日 / 全部」切换 + all 模式日期标记
- [x] 6. 考我页跟随 scope（复用 store.notes）

## 测试 + gate
- [x] 7. e2e：`GET /v1/notes` 跨天 + day 字段；note session 顺序修正
- [x] 8. `./scripts/gate.sh`（ruff + mypy + pytest 全绿）+ npm build
- [x] 9. sync openspec + 归档
