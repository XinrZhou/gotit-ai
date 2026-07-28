# Topic-session quiz — 考我模式改主题 session 聊天

> **Status: proposed 2026-07-28**

## Why

考我模式当前是「逐题考试」：选一道题 → 提交回答 → 判定 → 下一题，所以有「跳过」「提交回答」「删除此题」这些逐题操作。但一天学多个主题时，用户想要的是「选一个主题，直接和章鱼哥聊」——它围绕该主题的多个考点自主追问、流转，用户自然回答，像 ChatGPT 那样只有一个输入框 + 发送。

本变更把考我从「单 claim 多轮 + 逐题操作」改成「主题 session 多轮 + 聊天式」：选主题 → 进入该主题对话 → 章鱼哥自主穿梭该主题的多个 claim 追问 → 用户聊天回答。去掉题目 tab、跳过、提交、删除，统一成聊天交互。

## Scope

### In

- **后端**：
  - 新 DTO `TopicExamineVerdict`：`current_claim_id` / `done` / `verdict` / `follow_up` / `session_done`
  - `/v1/examine` 支持 `topic` 模式（传 `topic` + 可选 `answer`/`history`）；保留 `claim_id` 旧模式兼容现有测试
  - Axiom 拿到主题 + 该主题未 mastered 的 claim 列表，自主挑题追问，verdict 时带 `current_claim_id`
  - `done=true` 时 `apply_examine_verdict(current_claim_id, verdict)` 回写
  - `prompts/axiom.md` 加主题穿梭指令（多 claim 自主流转）
- **前端**：
  - 考我模式：主题 chip 行（保留）→ 选中主题进入对话
  - 去掉题目 tab、跳过、提交回答、删除此题
  - 底部聊天输入框 + 发送按钮（像回讲/项目深挖）
  - `session_done=true` 时显示「本主题都过了 ✓」
  - 主题 session history 只在前端 state（M0 不持久化，刷新丢；后续加 session 表）

### Out

- 主题 session history 持久化（M0 前端持有，刷新丢；后续加 session 表）
- 主题 session 跨天续聊（M0 每次进主题新开 session）
- 回讲 / 项目深挖模式（不动）
- claim 的 topic 抽取逻辑（Compass 负责）

## Non-goals

- 不改 claim/plan_item 数据模型
- 不改 verdict 三值映射（passed/almost/owe_next）

## Verification

- `./scripts/gate.sh` 全绿（含旧 claim_id 模式 e2e 回归）
- 考我模式：选主题 → 章鱼哥开场问该主题第一个 claim → 用户回答 → 追问或给 verdict 切下一 claim → 全部判完显示「本主题都过了」
- 无 claim_id 旧模式回归：`tests/test_e2e.py` 仍通过
- 前端：无题目 tab/跳过/提交/删除，只有输入框+发送
