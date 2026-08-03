# Proposal: verify-spine-deepen

## Why

验证脊柱已有「双 agent + 确定性门禁 + 分散的上下文上限」，但三处仍浅：
`score`/`evidence` 进门禁却被丢弃；harness 只有 CLI，无法在应用内对照后
adopt；再考上下文的预算常量分散，总长会叠加超标。

## What changes

1. **Gate signals** — `deterministic_gate` 在 stricter-of-two 之上，用可解释、
   有测试钉死的规则消费 `score`/`evidence`（仅降档，永不靠高分升档）。
2. **Harness holdout surface** — REST 触发/列出 run + 人工
   `adopt|observe|reject`（CLI 仍可用）。**Settings「Harness」曾试点后撤掉**
   （错面；工程台不进学习者设置）— 以 API/CLI 为准。
3. **ContextBudget** — `core/context_budget.py` 统一总字符预算与裁剪优先级；
   Axiom prompt 组装前 compose。

> **Status (2026-08-03):** tasks 已全部勾完；应归档进
> `archive/`（见 `main-path-converge` archive policy）。

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
