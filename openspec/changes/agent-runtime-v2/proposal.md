# Proposal: agent-runtime-v2

## Why

Verify Spine 已硬（Critic → `deterministic_gate` → `write_mastery_outcome`），
`state-boundary-tighten` 已收紧写口。下一阶段不是产品功能，而是把现有闭环
升级成可讲述、可回放的 **Mastery Agent Runtime 工程面**：

- Chat 与 verify 两套编排；掌握写回缺少统一 `run_id` / proposal→commit 边界
- 长期状态真相在 Claim/graph，但缺统一 **LearnerStateSnapshot** 投影
- Examine context 在 routes/MCP 多处手搓；`ContextBudget` 未升为可哈希的 Pack
- Harness 能防污染（dev/gold），缺 **holdout** 与 **Agent Run Replay**（改
  prompt/budget 如何证明不退化）

不推倒 Verify Spine。目标：契约先行、薄信封、verify-first——用 AI Coding
证明 Agent Application / Memory / Context / Eval 工程能力。

## What changes

按 Phase（与 Implementation Review 对齐；**本夹只开这一份**）：

1. **Phase 0（本文档）** — OpenSpec + ADR 0003/0004；冻结 Out / 验收
2. **Phase 1** — Replay harness + holdout suite；`gate.sh` 接入；adopt 绑
   `suite_version`
3. **Phase 2** — `LearnerStateSnapshot`（只读派生）+ `EvidencePack`；verify
   五入口收敛到 Pack（不强制 chat）
4. **Phase 3（可选加分）** — 薄包 `finalize_examine_with_gate`：`WriteIntent` /
   `run_id` / 幂等 commit；**不**统一 `chat_orchestrator`
5. **Phase 4（本夹后置）** — ToolSpec 副作用分级 + 只读 Run Trace（不做监控产品页）

## Out

- 改 `deterministic_gate` / schedule 阈值或公式
- Drill/Sage 过门；全量 MCP 挂进 chat；Multi-Agent 平台；auto-adopt prompt
- 新权威表承载「学习者画像」；LearnerState 落库当真相
- 重写 `chat_orchestrator` / 大改 chat prompt 组装（Phase 1–3）
- Web 主路径 / Done 条 / Brief 文案（属 `main-path-converge` /
  `verify-return-loop`）
- 通用 RAG / 第二大脑；多租户

## Success

1. 任意 verify 掌握写回可追溯契约（Phase 3：`run_id` + WriteIntent；Phase 1–2
   至少 replay 断言 gate/writeback）
2. 改 prompt/budget/routing：replay + holdout 红则不能合；adopt 绑 suite 版本
3. Verify 路径 LLM 上下文只经 `EvidencePack`（可打印 trim / `pack_hash`）
4. Chat 仍不能 authoritative 写 mastery（契约测试保持）
5. Gate 语义与 `write_mastery_outcome` 行为相对本夹基线 **不变**
6. 面试 5 分钟能指到代码锚点画清：LLM / Critic / Gate / Snapshot / Eval

## Impact

- **Core（后续 Phase）：** `context_budget`、新 `learner_state` / 可选
  `agent_run`；`harness` cases + `scripts/run_replay_harness.py`
- **API/MCP（Phase 2）：** `verify_attempt`、examine/teach routes + MCP tools
  改调 Pack；`verify_finalize` 仅薄包装（Phase 3）
- **Docs：** ADR 0003/0004；Phase 完成后短同步 `docs/SYSTEM.md`
- **无** Postgres 权威表 migration（audit 表若加则为可空加法，非本 Phase 0）
- **不**改 `web/` 产品行为

## Relation to other changes

| Change | 分工 |
|--------|------|
| `state-boundary-tighten` | 已完成：单写口 / prepare≠finalize — **本夹建立其上** |
| `main-path-converge` / `verify-return-loop` | UX 壳 — **本夹不碰** |
| `mastery-graph-deepen` 等 | 图谱/产品旁路 — **本夹不合并进任务** |
