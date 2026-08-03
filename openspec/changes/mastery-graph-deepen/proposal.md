# Proposal: mastery-graph-deepen

## Why

弱点图谱已有 verify 写回（`confused_with` / `depends_on` / fail_events）与全屏
力导向图，但偏「观察装饰」：点不开练、边因不明、跨主题结构看不清。

立意（学习科学 × 图表示，非百科 KG）：
- **前置** → `depends_on`；**相似干扰** → `confused_with`
- 边来自过门证据（公司 KG 经验：provenance + 用进决策）
- 图谱服务「今天欠什么 / 再考带什么」，不是第二大脑

## What changes

### Phase 1 — 用法
1. 点 claim → 按 `preferred_check_mode` 一键开考/回讲/深挖（复用 pending verify）
2. 点边 → 说明易混权重 / 跨主题 / 前置是否未过 / 最近失败摘要
3. 详情区安静 CTA（Apple quiet select）

### Phase 2 — 结构可读
1. `/v1/obs/graph` 节点/边 meta  enrichment（claim_id、topic、cross_topic、
   last_fail、unmet depends、preferred_check_mode）
2. 图上跨 topic 易混高亮；「近 14 天」筛选
3. Topic 簇既有着色保留并写清图例

### Later（本夹不做）
同场共挂新边；LLM 建议 depends；Neo4j / GraphRAG / 百科本体

## Out

- 主壳改成图谱；改 gate / 排程公式
- LLM 自动造边；笔记全文进图

## Success

- 从图能开练并关掉全屏图
- obs 边含 cross_topic / unmet 等可测字段
- 近 14 天筛选可用；gate 绿；SYSTEM 短同步

## Impact

- `db/ops/shell.py` build_graph、`db/ops/graph.py` helpers、tests
- `web/.../MasteryGraphPanel` + store queue verify
- `docs/SYSTEM.md`；本夹
