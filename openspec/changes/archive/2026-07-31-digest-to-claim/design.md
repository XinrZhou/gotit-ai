# digest-to-claim — design

## Boundaries

| 动 | 不动 |
|----|------|
| interest → claim 晋升流水线 | mastery gate、schedule 公式 |
| 动态页 / shell API | ChatPage 消息块组件 |
| 抽主张质量门槛（可规则+模型） | 资讯源爬虫大改 |

## Flow

```text
shell_event / interest（已有「有用」）
  → POST promote（user）
  → extract 1–3 claims（短、可检验；失败则返回 reason）
  → 可选写入 note stub + claims
  → 挂 plan_item 或 due 轻队列
  → 用户开考 → 现有 verify finalize
```

## API（示意）

- `POST /v1/shell/interests/{id}/promote` → `{ claims[], plan_item_ids? }`
- MCP 镜像；列表项带 `promoted_claim_ids` 避免重复晋升

## Quality

- 拒绝：纯情绪、无主体、不可证伪的空话（规则优先，模型辅助改写建议）
- 预算：单次最多 3 claims；上下文只注入该条资讯摘要

## Risks

- 与笔记 ingest 重复：晋升应复用 `ingest`/`curate` 原语，不复制一套抽取
- 用户误点有用：晋升必须二次确认或一键可撤销（软删 claim / 移出计划）
