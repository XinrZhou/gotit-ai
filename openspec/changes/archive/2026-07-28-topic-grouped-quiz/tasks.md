# Tasks — topic-grouped-quiz

- [x] 1. OpenSpec：proposal/tasks（本文件）
- [x] 2. 后端：`PlanItemView` 加 `topic: str | None`；`get_plan` 批量查关联 claim 的 topic 传给 `_plan_item_view`
- [x] 3. 前端：考我模式主题 chip 行（按 topic 聚合）+ 题目 tab 按主题筛选
- [x] 4. 前端：题目 tab 右侧 × 按钮，二次确认删除
- [x] 5. 前端：composer 移除左下「删除此题」，右下统一跳过/提交
- [x] 6. gate（ruff/mypy/pytest/npm build）+ 归档

## Delivery notes

- `PlanItemView` 加 `topic`，`get_plan` 批量查 `ClaimRow.topic` 构建 `topic_map` 带出，避免 N+1。
- 考我模式两级：主题 chip 行（`全部 · N` + 按 `claim.topic` 聚合，未分类归「未分类」）+ 题目 tab 行（当前主题筛选）。
- 题目 tab 改成 `claim-tab` 容器（main 按钮 + × 按钮），× 默认隐藏，hover 显示，点击弹确认 modal 二次确认后删除。
- composer 左下「删除此题」移除，右下只剩「跳过」「提交回答」。
- gate 全绿：ruff / mypy / pytest 7 passed / npm build ok。
