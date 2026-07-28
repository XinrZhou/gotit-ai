# Topic-grouped quiz — 考我模式按主题分组 + tab 删除

> **Status: proposed 2026-07-28**

## Why

考我模式当前是一排扁平的题目 tab，一天学多个主题（上下文工程/提示词工程）时题目混在一起，找不到重点。Claim 已有 `topic` 字段（agent-rewrite 加的），但 PlanItemView 没带出 topic，前端无法分组。另外「删除此题」按钮孤悬左下角，远离右侧主操作，位置不合理。

## Scope

### In

- **后端**：`PlanItemView` 加 `topic: str | None`，`get_plan` 批量从关联 claim 带出 topic
- **前端考我模式两级**：
  - 主题 chip 行：`全部 · N` + 按 `claim.topic` 聚合的主题 chip（未分类归"未分类"）
  - 题目 tab 行：只显示当前主题筛选下的题目
- **题目 tab × 删除**：每个题目 tab 右侧加 × 按钮，点击二次确认后删除
- **composer 操作区**：移除左下「删除此题」按钮，右下统一 `[跳过][提交回答]`；删除走 tab 上的 ×

### Out

- 回讲 / 项目深挖模式的交互（不动）
- 主题的新建/编辑（topic 来自 claim，不在前端直接编辑）
- 跨天主题聚合（只按今日 plan items）

## Non-goals

- 不改 claim 的 topic 抽取逻辑（Compass 负责）
- 不做主题的持久化筛选偏好

## Verification

- `./scripts/gate.sh` 全绿
- 考我模式：主题 chip 按今日题目 topic 聚合，点主题筛选题目 tab，未分类单独一组
- 题目 tab × 二次确认删除生效
- composer 右下只剩跳过/提交，无左下删除
