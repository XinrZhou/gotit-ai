# Agent brief — failure-writeback-regress（方向 B）

你负责把 **失败写回 → 再练注入 → 排程可审计** 做成可回归行为。

## 必读

1. `proposal.md` / `design.md` / `tasks.md`（本夹）
2. `docs/VISION.md` P2/P4/P7；`docs/PRODUCT.md` 核心闭环
3. 代码：`core/failure_lessons.py`、`db/ops/memory.py`、`verify_finalize.py`、
   `core/schedule.py`、axiom/echo 注入

## 目标

端到端契约可测；注入收口；排程表与代码一致。不扩产品面。

## 并行夹

`openspec/changes/eval-harness-loop/`（方向 A）会写 harness 断言吃你的 API。
保持纯函数/ops 稳定；不要改 harness runner 指标框架。

## 完成定义

- tasks 勾完；`./scripts/gate.sh` 绿
- SYSTEM 已短同步失败→再练
- 未接深挖过门、未上 FSRS/RAG、未改主路径 UX
