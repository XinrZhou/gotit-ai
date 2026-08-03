# Proposal: verify-spine-deepen

## Why

验证脊柱已有「双 agent + 确定性门禁 + 分散的上下文上限」，但三处仍浅：
`score`/`evidence` 进门禁却被丢弃；harness 只有 CLI，无法在应用内对照后
adopt；再考上下文的预算常量分散，总长会叠加超标。

## What changes

1. **Gate signals** — `deterministic_gate` 在 stricter-of-two 之上，用可解释、
   有测试钉死的规则消费 `score`/`evidence`（仅降档，永不靠高分升档）。
2. **Harness holdout surface** — REST 触发/列出 run + 人工
   `adopt|observe|reject`；Settings「Harness」页可跑 `dev`/`gold` 并决策。
3. **ContextBudget** — `core/context_budget.py` 统一总字符预算与裁剪优先级；
   Axiom prompt 组装前 compose。

## Out

- 完整 FSRS / 工业 CAT 重写
- 自动 adopt（人仍是 judge）
- score/evidence 前端卡片
- 全量 MCP catalog 挂进聊天
- 多用户 / OAuth

## Impact

- `gotit.core` gate + new context_budget；`GateResult.signals`
- REST `/v1/harness/*`；Settings 新 tab
- 测试：`test_gate_signals`、`test_context_budget`、`test_harness_api`
- `docs/SYSTEM.md` Not-done 项更新
