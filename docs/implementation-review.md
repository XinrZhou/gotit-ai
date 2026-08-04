# 实现评审 — Agent Runtime V2

> `openspec/changes/agent-runtime-v2/` 的工程决策日志。  
> 不是产品 backlog。不是 Verify Spine 重设计。  
> 日期：2026-08-03。状态：**Phase 0–3 已在代码落地**；Phase 4 可选未开工。

规范规格：`openspec/changes/agent-runtime-v2/{proposal,design,tasks}.md`  
ADR：`docs/adr/0003-learner-state-is-derived.md`、`docs/adr/0004-verify-run-envelope.md`  
路线图：`docs/agent-runtime-roadmap.md`  
面试包装：`docs/ai-engineering-story.md`

---

## 1. 为何是 verify-first + 薄信封（不是最初的大 Runtime）

早期 V2 草图描述了统一 chat / examine / teach / ingest 的完整 **Agent Runtime**（单一 `RunLifecycle`）。对照 **真实** 代码库，范围过大：

| 仓库事实 | 含义 |
|----------|------|
| Verify 路径已通过 `finalize_examine_with_gate` → `deterministic_gate` → `write_mastery_outcome` 闭环 | 掌握地板已在；不要替换它 |
| 聊天是独立的 `chat_orchestrator` + prepare-only 工具 | 把聊天塞进同一生命周期 = 大重写，Week-1 收益弱 |
| `state-boundary-tighten` 已强制单一掌握写口 + prepare ≠ finalize | V2 应 **叠契约**，不重开写平面 |
| Harness `dev`/`gold` 已证明防腐；当时缺 holdout / agent-run replay | 最高杠杆是 **先锁行为，再动结构** |

**已接受的收窄计划：**

```text
Eval Replay + Holdout
  → LearnerStateSnapshot + EvidencePack（仅 verify）
  → 可选薄包 finalize（run_id / WriteIntent）
  → 稍后 ToolSpec + Trace
```

**本变更拒绝：** 第一天跨全部表面的统一 Runtime。

---

## 2. 当前系统定位（诚实）

| 宣称 | 状态 |
|------|------|
| 以验证为中心的 **AI Agent Application** | **已上线** — 聊天壳 + 固定 verify 工作流 |
| Personal Mastery **Agent Runtime**（薄信封 + Snapshot + Pack + Replay） | **Phase 0–3 已落地** — 薄 verify 信封，**不是**统一多表面 OS |
| 多角色 Agent（Axiom / Critic / Echo / Sage / Compass） | **已上线** — 产品工作流内角色分工，非开放 Multi-Agent 平台 |
| 确定性掌握 Gate | **已上线** — VISION P7；`core/loop.py` |
| 离线 harness + 人工 adopt\|observe\|reject | **已上线** — 仅审计；**replay + holdout 已进 CI**（`gate.sh`） |
| adopt / 运行摘要钉 `SUITE_VERSION` | **已上线**（当前 `…phase3`） |

**今日一句话：** 以验证为中心的 Agent Application，其上叠了可回归的薄 Verify Runtime 工程层。  
**目标一句话：** Personal Mastery Agent Runtime（工程表面），掌握真相仍在脊柱上。

**面试可宣称：** Replay / Holdout、Snapshot、EvidencePack、propose→evaluate→commit 信封已在代码。  
**勿宣称：** 聊天已统一进 Runtime；ToolSpec / Trace 产品已上线；通用 Multi-Agent / RAG 平台。

---

## 3. 核心架构约束（不可破）

| ID | 约束 |
|----|------|
| C1 | `deterministic_gate` 是掌握法官 — 永不交给 LLM |
| C2 | 掌握 **行** 只经 `write_mastery_outcome`（verify 走 finalize；校准 / harness 显式 `source`） |
| C3 | Companion 工具：prepare ≠ 掌握写 |
| C4 | Drill / Sage **不过门** |
| C5 | `gotit.core` 保持无框架依赖 |
| C6 | REST ↔ MCP 共享 `db.ops` / 同一 finalize 路径 |
| C7 | 上下文有预算（VISION P4）；verify prompt 不默认塞生笔记 |
| C8 | `memory_entries` 不是掌握权威 |
| C9 | Adopt 仅审计；不自动改 prompt（VISION P5） |
| C10 | 本变更 **不** 改 Gate / 排程数值公式 |

冻结来源：ADR-0004 + `agent-runtime-v2` proposal Out。

---

## 4. 为何明确不做这些

### 大一统 Runtime（第一天 chat + verify + ingest）

- 成本 / 风险主导；聊天不是掌握写路径。
- ADR-0004：包 verify finalize；`chat_orchestrator` 重写延后（Phase 1–3 未做）。

### Multi-Agent 平台

- 产品需要诚实考试 + 陪伴，不是开放 supervisor / worker 协作。
- 五角色 ≠ multi-agent OS；叠编排会稀释 Verified = done。

### 通用 RAG / 第二大脑

- 掌握是 **claim / 排程 / 失败图状态**，不是检索命中率。
- 日后可选 claim 锚定检索也绝不能单独写掌握。向量库不当权威。

### LearnerState 做成权威表

- ADR-0003：Snapshot **仅派生投影**。
- 可写 learner-profile 表会变成 `ClaimRow` / 图旁的第二真相 —— 一致性税，无 AI Eng 收益。

---

## 5. 阶段拆分与验收

| Phase | 目标 | 验收（摘要） | 代码状态 |
|-------|------|--------------|----------|
| **0** | 规格 + ADR 锁定 | OpenSpec 三文件 + ADR 0003/0004；Out 明确 | **完成** |
| **1** | Replay + Holdout | ≥8 replay；holdout 隔离；`gate.sh` 接入；adopt↔`suite_version` | **完成**（2026-08-03） |
| **2** | Snapshot + EvidencePack | Builder + 测试；verify 调用方只用 Pack；聊天行为不变 | **完成**（2026-08-03） |
| **3** | Verify Run 信封 | 现有 finalize 外包 `run_id` / WriteIntent / 幂等 commit | **完成**（2026-08-03） |
| **4** | 工具策略 + Trace | 副作用分级 + 只读 Trace；短同步 SYSTEM | **未开工**（可选） |

Week-1 硬 DoD（当时评审）：Phase **0 + 1 + 2**；Phase 3 nice-to-have；Phase 4 不进 Week-1。  
**现状：** Week-1 DoD 与 Phase 3 均已完成。

完整清单：`openspec/changes/agent-runtime-v2/tasks.md`。

### Phase 1 完成说明（实际）

**代码已交付：**

- `src/gotit/harness/cases/replay.py` — 经后续 Phase 扩至 **12** 条（含 Pack / 信封）
- `src/gotit/harness/cases/holdout.py` — 5 条；门对与 gold 互斥
- `scripts/run_replay_harness.py` + `run_harness.py --set replay|holdout`
- `scripts/gate.sh` 跑 replay 再 holdout（失败非零）
- `SUITE_VERSION` 钉在每次 harness 摘要；`set_harness_decision` 始终写 `suite_version`

**相对计划（诚实差异）：**

| 计划项 | 实际 |
|--------|------|
| 经 stub LLM 做 Critic 降级 | stub_critic **回声** examine；降级用例把固定 recheck 注入 finalize 后同一 `deterministic_gate` + `write_mastery_outcome` 路径 |
| 幂等 commit 键 | Phase 1 锁双次 finalize 状态稳定；WriteIntent 幂等键在 **Phase 3** |
| EvidencePack / pack_hash | 当时属 Phase 2；trim 用例先用既有 `compose_examine_context` |

**未改：** Gate 阈值、排程公式、聊天编排器、Web UI。

### Phase 2 完成说明（实际）

**已交付：**

- `core/learner_state.py` — Snapshot 类型 + 纯 assemble / fingerprint
- `db/ops/learner_state.py` — 异步 `build_learner_state`（仅派生读）
- `EvidencePack` / `compile_evidence_pack`（`core/context_budget.py`）
- `db/ops/evidence.build_evidence_pack_for_claim` — verify 上下文单一入口
- 迁移：`verify_attempt`、examine / teach REST + MCP（无手搓 join）
- Replay：`replay-pack-hash-stable`；当时 `SUITE_VERSION` → phase2（现已 phase3）

**相对计划：**

| 计划 | 实际 |
|------|------|
| `build_learner_state` 在 core | 类型 / assemble 在 core；异步装载在 `db.ops` |
| 聊天消费 Snapshot | **延后** — 聊天编排器未动 |
| 所有 trajectory 行带 pack_hash | 挂在 thread-verify gate 消息 metadata；非每行 |

### Phase 3 完成说明（实际）

**已交付：**

- `core/agent_run.py` — `AgentRun` / `WriteIntent` / `CommitReceipt` + evaluate / reject 辅助
- `finalize_examine_with_gate` 包一层 propose → gate → commit；返回 `run_id`、`write_intent`、`commit_receipt`
- Trajectory 审计带 `run_id` + `idempotency_key`（**无**新权威表）
- 同 `run_id` 再 commit 幂等（不二次写掌握 / trajectory）
- Replay：`replay-envelope-gate`、`replay-rejected-intent`；幂等用例收紧
- `SUITE_VERSION` → `2026.08.03.agent-runtime-v2.phase3`

**LLM vs Code 边界（已锁）：**

| 关切 | 归属 |
|------|------|
| examine / recheck 裁决 | LLM（仅提案 → WriteIntent） |
| 掌握档 / 排程写 | Code：`deterministic_gate` 再 `write_mastery_outcome` |
| 被拒 WriteIntent | 不得 commit（`intent_may_commit`） |

**未覆盖：** 聊天 RunLifecycle、ToolSpec 注册表、Trace 看板、权威 run 表。

---

## 6. 编码禁令（Agent 与人）

执行 `agent-runtime-v2` 期间：

1. 不改 Gate / 排程 **语义或阈值**。
2. 不重写 `chat_orchestrator`（Phase 1–3；Phase 4 也不默认做）。
3. 不在本变更塞 Web 主路径 / Done 条 / Brief 产品活（其它 OpenSpec）。
4. 不加权威 learner-profile 表或发明掌握真相的迁移。
5. 不把全量 gotit MCP 挂进 companion 聊天。
6. 不从 harness 决策 auto-adopt prompt。
7. 不开并行 finalize — 只包或调用既有 `finalize_examine_with_gate` / `finalize_claim_by_id`。
8. 不扩成 Multi-Agent 平台、通用 RAG 或多租户鉴权。
9. 一次一个可提交故事；结构改动前先用 replay 锁行为。
10. 未合并对应 Phase 前，不在 `SYSTEM.md` 宣称 Runtime 能力（**Phase 0–3 已可宣称薄信封**）。

---

## 7. 与相关文档的关系

| 文档 | 相对本文件的角色 |
|------|------------------|
| `docs/v2_design.md` | 早期设计草图；**执行权威**是 OpenSpec + ADR；本评审记录 **收窄** |
| `docs/architecture_review.md` / `docs/project_analysis.md` | 分析基线；非任务跟踪器 |
| `docs/SYSTEM.md` | Agent onboarding 快照 — 已列出 Runtime V2 Phase 0–3 |
| `docs/agent-runtime-roadmap.md` | 前进路径；状态标签与 `tasks.md` 同步 |
| `docs/ai-engineering-story.md` | 面试收敛稿；勿写超出本评审的能力 |

---

## 8. 代码锚点（已上线 — 勿神话）

| 关切 | 路径 |
|------|------|
| Gate / VerifyWorkflow | `src/gotit/core/loop.py` |
| Context 预算 + EvidencePack | `src/gotit/core/context_budget.py` |
| LearnerStateSnapshot | `src/gotit/core/learner_state.py`、`db/ops/learner_state.py` |
| Evidence 装载 | `src/gotit/db/ops/evidence.py` |
| Run 信封类型 | `src/gotit/core/agent_run.py` |
| Finalize（含信封） | `src/gotit/api/verify_finalize.py` |
| 掌握写口 | `src/gotit/db/ops/claim.py` → `write_mastery_outcome` |
| Companion prepare 工具 | `src/gotit/api/companion_tools.py` |
| 聊天编排器 | `src/gotit/api/chat_orchestrator.py`（**未**统一进信封） |
| Harness | `src/gotit/harness/`、`scripts/run_harness.py`、`scripts/gate.sh`、`scripts/run_replay_harness.py` |
