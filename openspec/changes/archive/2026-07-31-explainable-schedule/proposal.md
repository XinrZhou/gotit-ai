# explainable-schedule

## Why

间隔复习与 `due_reason` 已有，但「为什么今天练这个」仍偏机器口吻；前置卡住时缺少轻量 `depends_on`，再练有时打在未备前置上。

对应 `docs/PRODUCT.md` 演进 §2：排程可解释；掌握档位与排程仍是代码。

## What changes

| 块 | 内容 |
|----|------|
| A | 增强 `due_reason_text`（失败次数、易混邻居、逾期）人话模板，确定性拼接 |
| B | 轻量 `depends_on` 边（手动或 curation 弱提示）；due 排序可略抬「前置未过」 |
| C | 再考注入：预算内带前置短标 + 易混；不塞整本笔记 |
| D | 弱点图谱只读展示 depends 边（若已有图 UI）；REST/MCP 字段 |

## Out

- LLM 决定 next_review_at 或掌握档位
- 完整知识图谱 / 第二大脑
- Chat 块 UI、digest、面试文案

## Acceptance

每条 due 有稳定可测的人话原因；存在 depends_on 时排序/注入行为有单测；gate 语义不变。

## Agent owns / do not touch

- **Owns:** `core/schedule.py`、graph depends 边、ops due 视图、`/v1/today` 字段、图谱只读、测
- **Do not touch:** Chat ActionBlocks、Bootcamp、day-close、digest promote、interview ramp 表
