# Tasks: failure-writeback-regress

> Agent：只做本夹。Web 主路径 UX 不要动。门禁：`./scripts/gate.sh`。

## 0. 摸底

- [x] 读 `core/failure_lessons.py`、`db/ops/memory.py`（digest/hints）、
      `db/ops/claim.py`（apply_examine_verdict）、`api/verify_finalize.py`、
      `core/agents/axiom.py`（build_prompt）、teach/echo 注入点、
      `core/schedule.py`、`tests/test_failure_*.py`、`test_schedule.py`
- [x] 列出「已测 / 未测 / 注入漏网」三点，改 design 排程表与代码对齐

摸底摘要（实现前）：
- **已测**：select 优先级、max_items、char budget、digest 同档去重、
  build_prompt 含块、schedule 三档公式、apply→schedule、brief hint
- **未测**：passed 不写 digest、不同 verdict 并存、seen_keys 去重、
  e2e digest→prompt、echo 同源注入、prior_failures 边界 due 语义
- **注入漏网**：`build_topic_prompt` 曾绕过 `compose_examine_context`（已收口）

## 1. Digest 写回

- [x] 确认 almost/owe_next 经 finalize→apply 必走 `maybe_record_failure_digest`
- [x] 单测：同 claim+verdict 二次不插入；不同 verdict 可并存（若产品如此）
- [x] passed 不写 failure_digest

## 2. 再练注入收口

- [x] Examine：`build_prompt`（或等价）稳定含 budgeted lesson；有测
- [x] Claim-bound teach：与 examine 同源 select+budget；有测或共享 helper 测
- [x] 去掉/合并绕过预算的旁路拼接
- [x] 预算：超长先裁 lessons（与 ContextBudget 优先级一致）；测 MAX_CHARS

## 3. 排程可审计

- [x] 按代码重写 design 排程表（与实现一致）
- [x] `test_schedule.py` 覆盖三档 + prior_failures 边界
- [x] （轻量）`due_reason` 关键 code 与表不矛盾；不重做模板大改

## 4. 供 A 的契约

- [x] 保证 `select_failure_lessons` / `budget_failure_lesson_block` /
      `maybe_record_failure_digest` 可被 harness 无 UI 调用
- [x] 若需，加 `core` 或 ops 级「跑一轮写回+选课」测试 helper（非 REST 新面）

## 5. 文档

- [x] `docs/SYSTEM.md`：失败→再练短段；排程三档一句；Not done 不写假承诺
- [x] 本夹 Success 自检

## 6. 门禁

- [x] `./scripts/gate.sh`

## Do not touch

- `web/` 空态/芯片文案（作者自管）；非 bug 不改 ChatPage
- Harness runner/指标上卷（属 `eval-harness-loop`）
- 深挖 `finish_drill_session` 接 finalize
- FSRS / LLM 排程 / RAG
