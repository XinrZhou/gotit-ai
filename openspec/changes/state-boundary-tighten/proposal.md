# Proposal: state-boundary-tighten

## Why

第一阶段验证闭环已成立（Claim → Critic → gate → writeback）。  
下一阶段问题不是「怎么考」，而是**状态越来越散**：

- 一次失败写多处（claim / trajectory / failure_digest / fail_events / graph）
- calibration 与 companion prepare 旁路写掌握相关状态
- 「一次练习」不是一等概念；Today 对 plan-open 解释弱
- Memory 既当偏好桶又当失败事实源

不推倒重写。目标：收紧边界，让一个人半年后还能迭代。

## What changes

按 P0→P3：

1. **P0** — 掌握写回经共享 `write_mastery_outcome`；verify 仍只走 `finalize_examine_with_gate`；calibration 显式 `source=` 走同一 writer
2. **P1** — 抽 `run_verify_attempt` 去重 chat/MCP verify；companion prepare 停软写 `IN_PROGRESS`
3. **P2** — failure_digest 补 follow_up / upsert；`prior_failures` 单源（trajectory）
4. **P3** — plan 挂 due_reason；Today 加 MasterySnapshot + lane

## Out

- 推倒 Gate / schedule 公式；Drill 改成过门
- 大 rename、全量 DB migration、新 Agent 框架
- 自动改 prompt；多租户
- P4 效果观测仪表盘（占位，本夹不做）

## Success

1. routes/mcp 不直调 `apply_examine_verdict`
2. prepare 不改 mastery；execute 才写
3. 再练注入能拿到 follow_up（当有证据句时）
4. Today 能答「为何今日这项」（due + plan-open）+ 轻量「我现在怎样」

## Impact

- `db/ops/claim|memory|calibration|day`，`api/verify_finalize`，companion / chat / mcp verify
- `docs/SYSTEM.md`；Web Today/Brief 消费新字段（最小）
- 无 Postgres migration（优先）
