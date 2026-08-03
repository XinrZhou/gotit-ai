# Tasks: daily-brief-semantic-cleanup

> 验收：`design.md` AC1–AC6。禁止改 gate / schedule / 新 Agent。

## 1. Spec lock

- [x] 确认 owed 定义：`dueClaims ∪ plan-open`；notes **不**入 owed
- [x] 确认无 owed → 不渲染「欠」标题 Brief（账清 / 无料空态）
- [x] 确认笔记可考策略：默认移出 Brief（若做次要区须无「欠」字）

## 2. Implement（web only）

- [x] `ChatPage`：收紧 `hasDailyBrief`（及空线程同等逻辑）= `owed.length > 0`（且 !closed && !bootcamp）
- [x] `DailyBrief`：主列表只组装 owed；去掉（或降级）note 行
- [x] plan-open 无 due reason 时：诚实 meta（如「今日计划」）
- [x] 计数 /「全部 N」只含 owed
- [x] 无 owed 且库内仍有料：账清人话空态（不假 Brief）

## 3. Docs

- [x] `docs/SYSTEM.md`：简报「欠」= due + 今日未核销计划（一句）
- [x] 本夹保持活跃直至 AC 手测过；`openspec/changes/README.md` 已挂 active

## 4. Gate

- [ ] 手测 AC1–AC5（作者）
- [x] `cd web && npm run build`
- [ ] 提交（用户要求时）：`fix(web): keep DailyBrief owed-only`（或等价）；勿与 P0-2/P0-3 混提交

## Out / Later（本夹不做）

- [ ] P0-2 考完回程 CTA → 已开 **`verify-return-loop/`**
- [ ] P0-3 入口抢戏 — 建议 6.2 后真用再决定
- [ ] Examine/Teach picker 与 Brief 完全对称（可选 follow-up）
