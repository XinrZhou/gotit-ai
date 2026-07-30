# workflow-in-thread — 工作流回合写入同一 thread 消息流

## Why

Chat 宣称拥有表面，但考我 / 回讲 / 深挖回合活在 React 临时态或
`drill_sessions.messages` 里，thread `messages` 几乎看不到验证过程。
回到对话后证据链断裂，违背「companion owns the conversational surface」。

## Scope

### In

- Examine / Teach / Drill 每轮（含首问）可选写入当前 thread：`role` +
  `agent_name` + `metadata.workflow`
- 请求体 / MCP 工具增加可选 `thread_id`；缺省时行为与今日一致（不写 thread）
- Web：进入工作流时绑定（必要时新建）active thread，并把 `thread_id` 传给 API
- Chat 历史气泡对 `metadata.workflow` 显示安静徽章（考我 / 回讲 / 深挖）
- REST ↔ MCP 对等；pytest 覆盖写回与归属校验

### Out

- 废除专页 UI / 整栏替换（仍可嵌 ExaminePage 等）
- 用 thread 历史完全替代客户端 `history` 回传（过渡期两者并存）
- 删 `drill_sessions.messages` 或 `chat_messages` 遗留表
- Agent 自主 tool-calling 拉起工作流（另案）
- `/verify` 中间轮展开（终态 gate 消息已有）

## Verification

- `POST /v1/examine|teach|drill/...` + `thread_id` → `GET .../messages` 可见对应回合
- 非法 / 他用户 thread → 400/404，不写库
- 无 `thread_id` 时既有测试仍绿
- `cd web && npm run build`；SYSTEM / README 去掉该「Not done」项
