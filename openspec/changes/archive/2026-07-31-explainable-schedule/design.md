# explainable-schedule — design

## Boundaries

| 动 | 不动 |
|----|------|
| due 文案模板、depends_on 边、注入预算 | gate 阈值、Critic |
| `/v1/today` / graph 只读 | Chat UI 大改 |

## A — 人话模板（代码）

已有 `due_reason_code`。扩展 text 模板例：

- `overdue` →「已过建议复习日 n 天」
- `almost` →「上次还差点，今天接着」
- `confuse` →「易与「X」搞混」
- `depends` →「前置「Y」尚未过关」

禁止模型生成 next_review_at。

## B — depends_on

- 边存 Postgres（与 confuse 并列）；创建/更新走 ops（人工或 curate 建议 + 用户确认）
- 排序：前置未 `passed` 的 claim 可降优先或标「先补前置」（产品选一种，单测钉死）
- 注入：Axiom 预算内短标，计入既有 token 预算

## Risks

- 边爆炸：每 claim 出边上限（如 3）
- 与 confuse 混淆：类型字段分开，UI 图例区分
