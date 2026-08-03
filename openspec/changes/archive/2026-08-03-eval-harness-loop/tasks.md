# Tasks: eval-harness-loop

> Agent：只做本夹。UX / Chat 文案 / 深挖文案不要动。门禁：`./scripts/gate.sh`。

## 0. 摸底

- [x] 读 `harness/__init__.py`、`cases/dev.py`、`cases/gold.py`、`api/routes/harness.py`、`db/ops/harness.py`
- [x] 列出现有 case_id 与 metrics；对照 design 指标契约标缺口

## 1. 指标契约

- [x] 约定 `summary` 上卷字段（至少：`gate_consistent`、`routing_ok`、`no_spurious_write`、`failure_hook_ok`；保留 total/passed/failed）
- [x] `finalize_harness_run` 或 runner 末尾聚合；单测钉死键名
- [x] CLI / REST 返回体带上同一 summary（无破坏现有客户端则仅加法）

## 2. Dev case 加深

- [x] Gate 信号 / stricter案 metrics 可上卷（复用或扩展现有 deterministic_gate case）
- [x] check_routing case → `routing_ok`
- [x] stub / 无写回假 passed case → `no_spurious_write`
- [x] failure 钩子 case → `failure_hook_ok`（契约对齐 `failure-writeback-regress`；B 未合入时策略见 design）

## 3. 人审可追溯

- [x] 确认 PATCH decision 不触发 prompt/skill 副作用（测或断言代码路径）
- [x] （可选）list runs 支持按 decision 过滤

## 4. 文档

- [x] 更新 `docs/SYSTEM.md`：评测闭环短段 + Not done（仍无自动 adopt / 无 Harness UI）
- [x] 本夹 proposal Success 勾选条件自检

## 5. 门禁

- [x] `./scripts/gate.sh`
- [x] 不强制 `npm run build`（无 Web 改动）

## Do not touch

- `web/` 产品文案与空态（作者自管）
- `main-path-converge` 验收项
- LangGraph 引入、RAG、自动 adopt
- 大改 `verify_finalize` 业务语义（修 bug / 为 case 暴露纯函数除外）
