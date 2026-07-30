# chat-shell — design

## Layout

1. **Library = overlay drawer** at all breakpoints（absolute left, soft shadow,
   scrim on narrow）. Opening never changes chat column widths.
2. **Workflows in conversation chrome**：quiet chips at top when `mode === "chat"`;
   existing `ModeHeader` when in a workflow.
3. **Composer tray**：default textarea + send；`+` toggles agents/skills.
4. **Thread row**：single line — title ellipsis + tabular time.
5. **Library empty**：one empty copy + CTA when notes+projects empty.
6. **Narrow (`≤820px`)**：nav ~72px icon rail.

Apple：quiet `--fill` select；no ink rings/bars；primary CTA may stay solid ink.

## Interaction — backend

- `db.ops.thread.delete_thread`：校验 `user_id`；删 messages → ball → thread。
- `update_thread_title` + 发消息时 `touch` `threads.updated_at`。
- `post_message_chain`：首条 user（或标题仍为「新对话」）→ `derive_thread_title`；
  `AgentReply` 可选带 `thread`。
- `ChatTurn.thinking`；落库 `metadata.thinking`（与 handoff 并存）。
- `compose_system_prompt`：中文昵称身份卡；chat 路径 `include_rubric=False`。

## Interaction — frontend

- 「+ 新对话」：`POST /v1/threads { title: "新对话" }`，无 `window.prompt`。
- `send`：乐观 user + thinking 行；成功替换；失败保留乐观气泡并由 agent 错误气泡承接。
- `metadata.thinking` → 可折叠「思考过程」（无填充 pill；桩/过短不展示）。
- Stream + composer 居中阅读柱（`max-width: 720px`），左右气泡同属一栏。
- 顶栏「开一场验证」+ workflow chips；进入后 ModeHeader「正在考我/回讲/深挖」+ hint。
- 已选 skill → composer meta 安静 chip（可一键清除）；关 tray 仍可见。
- 连续同文 agent 气泡折叠；prompt 禁止已介绍后再重复自我介绍。
- thread 列表 hover 删除；删当前则切最近或空态。
- 打开/切换时 @搭子默认 = 该 thread 最后一条 agent 的 `agent_name`。

## Title heuristic

```text
strip + 压空白；≤28 字原样；否则截断加 …
```
