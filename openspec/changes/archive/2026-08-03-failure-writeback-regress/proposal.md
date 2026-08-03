# Proposal: failure-writeback-regress（方向 B）

## Why

产品立意「失败有用」（VISION P2）与 JD 高频的 Memory / 上下文工程，都要求：
挂过 → 留下可再用痕迹 → 再练时带着教训，且上下文有预算。

代码已有：`maybe_record_failure_digest`、`failure_lessons` 选择/预算、
DailyBrief `failure_hint`、finalize 后 trajectory / mastery graph、
`schedule` + `due_reason`。缺口是**端到端可回归**：去重、注入路径、
与排程档位一致的可审计表，避免「机制存在但行为漂移」。

本变更沿脊柱加深写回，不拉新垂直面、不改 gate 公式（除非测出 bug）。

## What changes

1. **端到端契约**：`almost|owe_next` → digest（claim+verdict 去重）→
   再 examine（及 claim-bound teach）注入 budgeted lesson 块；断言可测。
2. **注入路径收口**：Axiom / Echo 组装 prompt 时走同一套
   `select_failure_lessons` + `budget_failure_lesson_block`（已有则补洞、
   去掉旁路重复逻辑）。
3. **排程可审计表**：文档 + 单测钉死
   `passed|almost|owe_next` → `next_review_at` / 是否仍 due；
   `due_reason_*` 与表一致（不重做 explainable-schedule 大功能）。
4. **与 A 协作**：暴露稳定纯函数/ops 供 harness case 调用。

## Out

- 工业 FSRS / 用 LLM 决定 next_review_at
- 完整 KG / RAG 笔记仓
- 深挖接 `verify_finalize`（prep-only 冻结，本夹不碰）
- 微信推送文案/OpenClaw skill 大改（MCP pending list 保持可用即可）
- Chat/空态 UX 打磨（作者自管）

## Success

- 单测覆盖：去重、优先级（同 claim → confuse → topic）、字符预算裁剪
- 至少一条 DB/集成测：finalize owe_next → digest → 再 build_prompt 含教训且 ≤ cap
- 排程表有测；`docs/SYSTEM.md` 短述「失败→再练」
- 不改变「门是代码」语义

## Impact

- 主改：`core/failure_lessons.py`、`db/ops/memory.py`、`db/ops/claim.py`、
  axiom/echo prompt 组装、`core/schedule.py`（仅文档化/测/修不一致）、
  `tests/test_failure_*.py`、`test_schedule.py`
- 次要：SYSTEM；供 A 使用的稳定 API
- **不改** Web 主路径文案（除非暴露字段 bug）

## Agent handoff

见 `AGENT.md`。并行夹：`eval-harness-loop`（方向 A）。
