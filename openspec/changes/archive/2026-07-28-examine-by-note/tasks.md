# Tasks — examine-by-note

## 后端

- [x] 1. `db/ops.list_note_claims(note_id, user_id)`：取该笔记未 mastered claims，按 id
- [x] 2. `api/routes.ExamineRequest` 加 `note_id`；`/v1/examine` 加 note 模式分支（note_id > topic > claim_id）
- [x] 3. `mcp/server.gotit_examine` 加 `note_id` 参数

## 前端

- [x] 4. `store`：`examineTopic` → `examineNote`；`onExamineStart(note)` 调 note_id；`onExamineAnswer` 调 note_id；删 `onFillQueue`、`topics`
- [x] 5. `ExaminePage`：去主题 chip，改今日笔记入口列表（`标题 · N 题`，N=0 不显示）+ session 对话
- [x] 6. `Shell`：examine mode 去掉「补回顾」按钮

## 测试 + gate

- [x] 7. `tests/test_e2e`：加 note 模式（首轮 + 答题切 claim + session_done + 空笔记）；旧 topic/claim_id 回归
- [x] 8. `./scripts/gate.sh`（ruff + mypy + pytest 全绿）+ npm build + 手测
- [x] 9. sync openspec + 归档 examine-by-note
