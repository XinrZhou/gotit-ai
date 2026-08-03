# Agent brief — eval-harness-loop（方向 A）

你负责把 **Harness 评测闭环** 做实，不是改学习 UI。

## 必读

1. `proposal.md` / `design.md` / `tasks.md`（本夹）
2. `docs/SYSTEM.md`（Iron：gate 是代码；REST↔MCP 同构）
3. 代码：`src/gotit/harness/`、`api/routes/harness.py`、`scripts/gate.sh`

## 目标

固定指标契约 + 加深 **不烧 LLM** 的 dev cases + 人审仍只审计。

## 并行夹

`openspec/changes/failure-writeback-regress/`（方向 B）拥有失败写回行为。
你写 harness **断言**；不要在 B 的核心文件里大改产品逻辑。交界见 design §协作。

## 完成定义

- tasks 勾完；`./scripts/gate.sh` 绿
- SYSTEM 已短同步评测段
- 未引入 Harness UI / 自动 adopt / RAG
