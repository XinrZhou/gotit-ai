# Agent Runtime 路线图

> 从今日的 **以验证为中心的 AI Agent Application**，走向工程目标  
> **Personal Mastery Agent Runtime**。  
> 变更跟踪：`openspec/changes/agent-runtime-v2/`。  
> 配套评审：`docs/implementation-review.md`。  
> 面试包装：`docs/ai-engineering-story.md`。  
> 最近更新：2026-08-03。

状态图例：

| 标签 | 含义 |
|------|------|
| **已实现** | 已在 `src/` / CI；面试可宣称已上线 |
| **实施中** | 规格已接受；正在实现或即将开做 |
| **未来规划** | 在本路线图范围内，尚未开工 |
| **明确不做** | 本条轨迹拒绝（见评审 / ADR） |

---

## 当前状态 — 已实现

**以验证为中心的 AI Agent Application**（产品形态）+ **薄 Verify Runtime 信封**（工程层，Phase 0–3）

```text
Chat / MCP 表面
  → 角色 Agent（examine / teach / drill / chat 工具）
  → Critic + deterministic_gate
  → write_mastery_outcome（+ trajectory / 失败图）
```

代码里已成立（非穷尽；见 `docs/SYSTEM.md`）：

- 固定 Verify Spine；Gate 是代码（VISION P7）
- 单一掌握行写口；prepare ≠ finalize（`state-boundary-tighten`）
- REST ↔ MCP 共享领域 ops
- verify 路径：`LearnerStateSnapshot` + `EvidencePack`（预算 / `pack_hash`）
- 薄 Verify Run 信封：`AgentRun` / `WriteIntent` / `CommitReceipt`；`run_id` + 幂等键
- 离线 harness：`dev` / `gold` + **replay** + **holdout**；adopt 钉 `suite_version`（仅审计）
- Companion 工具白名单（prepare-only 的 open_* CTA）
- Drill **不过门**

**尚未成立（勿过度宣称）：**

- 聊天与 verify 仍是 **两条** 编排路径
- 聊天 **尚未** 消费 LearnerStateSnapshot / EvidencePack
- 无 ToolSpec 注册表 / 可观测 Trace API（Phase 4，可选）
- 无「学习者成效 → Agent 策略」闭环

当前 `SUITE_VERSION`：`2026.08.03.agent-runtime-v2.phase3`

---

## 目标状态 — 未来目标（工程）

**Personal Mastery Agent Runtime**（在已有脊柱上的工程表面）

```text
Verify 表面
  → LearnerStateSnapshot（派生）+ EvidencePack
  → 薄 Run 信封：propose → evaluate → commit
  → Replay + Holdout 护栏
  → （可选）ToolSpec 策略 + 只读 Trace
```

聊天仍是一等 **产品** 表面；面试可信 **不要求** 聊天共享完整 RunLifecycle。掌握真相仍在 claims / 图 / 排程。

---

## 演进阶段

### Phase 0 — 规格 / ADR

| | |
|--|--|
| **状态** | **已实现**（文档） |
| **目标** | 写代码前冻结 Out、成功标准、ADR |
| **技术价值** | 防止范围渗入 UX / 大一统 Runtime |
| **面试价值** | 展示判断力：Runtime = 信封，不是口号式重写 |
| **明确不做** | 业务代码；重设计 Gate；宣称 Runtime 已上线 |

已交付：

- `openspec/changes/agent-runtime-v2/{proposal,design,tasks}.md`
- `docs/adr/0003-learner-state-is-derived.md`
- `docs/adr/0004-verify-run-envelope.md`

---

### Phase 1 — Replay + Holdout 评测

| | |
|--|--|
| **状态** | **已实现**（2026-08-03） |
| **目标** | 无真实 LLM 下锁住 verify / gate / 写回契约；holdout 隔离 |
| **技术价值** | Pack / 信封改动前的回归网；VISION P5 长牙 |
| **面试价值** | 「如何知道改 prompt / 预算没有回退？」 |
| **明确不做** | Holdout 产品 UI；auto-adopt；为过 case 改 Gate 阈值 |

**实际落地：**

- Replay：`harness/cases/replay.py`（经 Phase 2–3 扩至 **12** 条，含 Pack / 信封用例）
- Holdout：5 条，`harness/cases/holdout.py`（与 gold 门对互不重叠）
- 入口：`scripts/run_replay_harness.py`；`run_harness.py --set replay|holdout`
- CI：`gate.sh` 在 dev harness 后跑 replay + holdout（失败非零退出）
- 版本钉：`gotit.harness.SUITE_VERSION`；adopt 始终记录

**相对计划的诚实差异（Phase 1 当时）：**

- Critic「降级」用例：注入固定 recheck 进同一 gate+写路径（stub Critic 本就会回声 examine）
- 幂等：Phase 1 锁「重复 finalize 状态稳定」；WriteIntent 幂等键在 Phase 3
- EvidencePack 当时未做（Phase 2）

---

### Phase 2 — LearnerStateSnapshot + EvidencePack

| | |
|--|--|
| **状态** | **已实现**（2026-08-03） |
| **目标** | 派生学习者投影 + 预算化上下文编译器，挂在 **verify** 路径 |
| **技术价值** | Memory 分类学且不造第二真相；消灭手搓 examine 上下文拼接 |
| **面试价值** | Memory Architecture + Context Engineering，有代码锚点 |
| **明确不做** | Learner 权威表；强迫聊天吃 Pack；通用 RAG |

**实际落地：**

- Snapshot：`core/learner_state.py` + `db.ops.build_learner_state`
- Pack：`compile_evidence_pack` / `EvidencePack.pack_hash`（`context_budget.py`）
- 装载：`db.ops.build_evidence_pack_for_claim` — verify_attempt、examine、teach（REST + MCP）
- 测试：`test_learner_state`、pack hash/trim 单测 + `replay-pack-hash-stable`
- 聊天编排器 **未改**

**相对计划：** 异步 builder 留在 `db.ops`（core 保持无框架）；聊天迁 Pack 延后。

---

### Phase 3 — Verify Run 信封

| | |
|--|--|
| **状态** | **已实现**（2026-08-03） |
| **目标** | 薄包一层 finalize：WriteIntent / `run_id` / 幂等 commit |
| **技术价值** | 显式 propose → evaluate → commit；掌握写可审计 |
| **面试价值** | 「生产 Agent = 带 commit 边界的状态机」 |
| **明确不做** | 统一 chat+verify Runtime；并行第二条 finalize；新权威表 |

**覆盖范围（实际）：**

- `AgentRun` / `WriteIntent` / `CommitReceipt`（`core/agent_run.py`）
- `finalize_examine_with_gate` 信封；trajectory 带 `run_id` + 幂等键
- Replay：`replay-envelope-gate`、`replay-rejected-intent`；同 run 幂等 commit

**未覆盖：**

- 聊天编排器统一
- 持久 AgentRun 表 / Trace API（Phase 4）
- 被拒 Intent 的产品化 abort UX（提交守卫已够）

---

### Phase 4 — 工具策略 + Trace

| | |
|--|--|
| **状态** | **未来规划**（可选；面试非必须） |
| **目标** | `ToolSpec` 副作用分级；只读 run Trace；短同步 SYSTEM |
| **技术价值** | 工具策略即代码；区分模型 / 工具 / Gate 故障 |
| **面试价值** | 工具治理 + 可观测，不做监控产品戏 |
| **明确不做** | 全量 MCP 进聊天；花哨运维看板；改动 prepare ≠ finalize |

---

## 横切：整条路线明确不做

| 项 | 原因 |
|----|------|
| 第一天大一统 Runtime | ADR-0004；成本 / 风险 |
| Multi-Agent 协作平台 | 稀释 Verified = done |
| 通用 RAG / 第二大脑 | 掌握 ≠ 检索 |
| LearnerState 权威表 | ADR-0003 |
| LLM-as-gate / auto-adopt | VISION P7 / P5 |
| Drill 过门 | 产品铁律 |
| 本变更内做 Web 主路径 | 其它 OpenSpec 管 UX |
| 改 Gate / 排程公式 | 本变更冻结 |

---

## 建议阅读顺序

1. `docs/SYSTEM.md` — 学习者今日已上线什么  
2. `docs/ai-engineering-story.md` — 面试收敛稿  
3. 本路线图 — 工程走到哪  
4. `docs/implementation-review.md` — 为何收窄计划  
5. `openspec/changes/agent-runtime-v2/` — 可勾选任务  
6. ADR-0003 / ADR-0004 — 不可谈判决策  

某 Phase 合并后：更新 `tasks.md` 勾选 → 本文件状态标签 → 若 onboarding / 架构叙事漂移则改 `docs/SYSTEM.md`。
