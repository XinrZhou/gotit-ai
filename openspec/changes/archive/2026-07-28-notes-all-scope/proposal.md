# notes-all-scope — 资料支持「今日 / 全部」两种范围

> **Status: proposed 2026-07-28**

## Why

侧栏资料目前只显示选中日期的笔记，历史资料要手动切日期才能看到、才能考。社招准备管家需要跨天复习历史资料。加一个「全部」范围，跨天列出所有笔记，从任意历史笔记直接进考我 session（`list_note_claims` 已不限日期，复习自然成立）。

## Scope

### In

- **后端**
  - `DayNoteView` 加 `day: date` 字段（从所属 learning_day 填充）
  - `db/ops.list_all_notes(user_id)`：跨天列所有笔记，按 created_at 倒序
  - `GET /v1/notes` 路由（返回全部笔记）
- **前端**
  - store 加 `noteScope: "today" | "all"`、`allNotes: DayNote[]`；scope=all 时取 allNotes，否则取今日 notes
  - 侧栏资料区顶部加「今日 / 全部」切换；全部模式下每条笔记显示日期
  - 考我页入口跟随当前 scope（复用 store 的 notes）
- **测试**：e2e 加 `GET /v1/notes` 返回跨天笔记 + day 字段

### Out

- 不做间隔重复复习队列（留作后续「复习」模式）
- 不改回讲 / 项目深挖

## Non-goals

- 不改笔记创建/ingest 逻辑
- 不加搜索/标签（后续挂在「全部」视图上）

## Verification

- `./scripts/gate.sh` 全绿
- 切「全部」：侧栏列出跨天所有笔记（带日期），考我页入口也跟随；选一条历史笔记能开考
- 切「今日」：回到只看选中日期
