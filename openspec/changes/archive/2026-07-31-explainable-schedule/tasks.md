# explainable-schedule — tasks

## A — Schedule + graph

- [x] 人话模板单测（code→text 稳定）
- [x] `depends_on` 模型 + alembic；出边上限
- [x] due 排序/标记策略 + 注入预算

## B — Surfaces

- [x] `/v1/today` 与 MCP 字段
- [x] 图谱只读展示 depends（若改动 `obs/graph`）
- [x] 可选：claim 上添加依赖的最小 API（无大 UI 也可先 API）

## C — Docs / gate

- [x] pytest
- [x] `docs/SYSTEM.md`：depends_on 从 Not done 挪到 Shipped（若完成）或改表述
