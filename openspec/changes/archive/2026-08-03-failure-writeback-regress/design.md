# Design: failure-writeback-regress

## 现状（代码事实）

| 步骤 | 路径 | 状态 |
|------|------|------|
| 写 digest | `db/ops/memory.maybe_record_failure_digest`；`claim.apply_examine_verdict` 触发 | 有；claim+verdict 去重 |
| 选课 | `core/failure_lessons.select_failure_lessons` | 有；prio 0/1/2 |
| 预算 | `budget_failure_lesson_block`；MAX_ITEMS=3 MAX_CHARS=600 | 有；单测 `test_failure_lessons.py` |
| Brief 提示 | `failure_hints_by_claim` → `/v1/today` | 有 |
| Examine 注入 | `axiom.build_prompt` + ContextBudget | 有；单测钉住 |
| Teach 注入 | Echo / teach 经 `build_failure_lesson_block` | 有；与 examine 同源 |
| Topic 注入 | `axiom.build_topic_prompt` + ContextBudget | 已收口（曾漏网旁路） |
| 轨迹 / 图谱 | `verify_finalize` → trajectory + `record_verify_mastery_writeback` | 有 |
| 排程 | `core/schedule.schedule_after_verdict` + `explain_due_reason` | 有；需「档位→行为」表+测对齐 |

已归档：`companion-tools-and-schedule`、`explainable-schedule`、failure 相关随 daily-verify / mastery。

## 端到端契约（SHALL）

```text
gate_verdict ∈ {almost, owe_next}
  → memory kind=failure_digest（同 claim_id+verdict 不重复插入）
  → 再次 examine（同 claim 或 confuse 邻）时
      prompt 含 budgeted failure lesson 块（或可观测的等价注入）
  → 块字符 ≤ FAILURE_LESSON_MAX_CHARS；条数 ≤ MAX_ITEMS
passed
  → 不新增 almost/owe_next digest；next_review 按 schedule 表 clear due
```

`owe_next` 与 `almost` 的排程差异必须与下表一致（数值以 `schedule.py` 为准，
表是文档契约；若代码与旧文档冲突，**以代码为准并更新 SYSTEM**）。

### 排程可审计表（与 `core/schedule.py` 一致；`test_schedule` 钉死）

给定 `as_of`（学习日）与 `prior_failures`（本 claim 此前未过关次数）：

| gate_verdict | next_review_at | reason_code | 当日 due？（本 claim，相对 `as_of`） |
|--------------|----------------|-------------|--------------------------------------|
| `passed` | `None`（清除） | `passed_clear` | 否 |
| `almost` | `as_of`（+0d） | `almost_today` | 是 |
| `owe_next` | `as_of + min(30, 1 + 2×prior_failures)` | `owe_scheduled` | 否（间隔 ≥1；到期日当天再 due） |

`MAX_INTERVAL_DAYS = 30`。例：`prior_failures=0→+1d`，`1→+3d`，`2→+5d`，`≥15→+30d`。

## 注入收口

- 唯一推荐入口：`select_failure_lessons` → format/budget → ContextBudget compose。
- Examine 必走；claim-bound teach 必走（与 examine 同教训源）。
- 禁止第三套「临时拼接 follow_up」绕过预算。
- `learner_failure_hint` / DailyBrief 可继续短提示，但不替代 examine 注入块。

## 去重与邻居

- Digest 去重：`(claim_id, verdict)` 已有 — 测「二次同档不插」。
- 选择：同 claim → `confused_with` 邻 → 同 topic；`seen_keys` 防双档重复行。
- 测：邻居 id 集合来自 graph ops；无邻时不炸。

## 协作（与方向 A）

| 事项 | Owner |
|------|--------|
| 稳定导出：select/budget/digest ops | B（保持可 import） |
| harness `failure_hook_ok` case | A |
| gate 公式 / score 降档 | 不在本夹；属 core/loop，只读 |

## 非目标

不改深挖 finalize；不用 LLM 写 next_review；不做 UX 空态；不扩 OpenClaw 文案。
