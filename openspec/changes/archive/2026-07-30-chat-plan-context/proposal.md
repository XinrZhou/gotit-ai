# chat-plan-context — Chat 注入今日计划摘要

## Why

Web 搭子问「今天的计划」时没有 `plan_items` 上下文，只能空转或编造。
计划数据在 REST / MCP / digest / Reminders 已通，Chat 未接。

## Scope

### In

- 每轮 `run_chat` 注入当日计划短摘要（标题 / 状态 / `due_time`）
- 空计划明说「还没有」；禁止编造条目
- 编排层用 `db.ops.get_plan`（Asia/Shanghai 当日）；REST ↔ MCP 共用
  `post_message_chain`，天然对等
- pytest：格式化 + prompt 含计划段

### Out

- Agent 本地 tool 调 `gotit_today`（后续阶段）
- 在对话里改计划 / fill-queue
- 改 verify / A2A 语义

## Verification

- 有计划时 prompt 含条目标题；空计划含「还没有」
- 相关 pytest 绿；SYSTEM / README 记一笔
