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
- `send`：乐观 user + thinking 行；成功替换；失败回滚。
- `metadata.thinking` → 可折叠「思考过程」。
- thread 列表 hover 删除；删当前则切最近或空态。
- 打开/切换时 @搭子默认 = 该 thread 最后一条 agent 的 `agent_name`。

## Title heuristic

```text
strip + 压空白；≤28 字原样；否则截断加 …
```
