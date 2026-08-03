# Gotit V2 — AI Native Engineering 演进设计

> **目标：** 把 gotit 打造成大厂 AI Application / Agent Engineer 面试代表项目。  
> **非目标：** 普通业务功能、产品增长、页面功能堆砌。  
> **北星：** 证明 AI Native Engineering 能力——不是功能更多。  
> 锚定：`docs/SYSTEM.md`（现状）、`docs/PRODUCT.md` / `docs/VISION.md`（硬约束）。  
> 起草：2026-08-03。

---

## 0. 面试叙事前提

多数候选人展示：**Chat + RAG + Tool Calling 演示**。  
Gotit 已有更硬的差异化，V2 叙事应升级为：

> **一个以「掌握终审」为硬边界的 Agent Runtime**：LLM 负责生成与陪伴，**确定性代码负责裁决与写回**；Memory / Tools / Eval 都是一等公民，而不是 prompt 周边。

| 能力 | 面试官真正在看什么 |
|------|-------------------|
| Judgment boundary | LLM 与代码的责任切分 |
| State authority | 谁能写 mastery / 谁只是 cache |
| Closed-loop agents | Plan → Act → Eval → Writeback |
| Context engineering | 预算、优先级、可证明的 trim |
| Eval as CI | 改 prompt/skill 有回归证据 |
| Tool policy | 白名单、副作用分级、可审计 |

**不可削弱（继承 VISION / PRODUCT）：**

- Verified = done；gate 是确定性代码，永不交给 LLM
- 失败有用；上下文有预算；人格服务判断尺度
- REST ↔ MCP 共享 `db.ops`；个人单用户，非多租户平台

---

## 1. 项目 V2 定位

### V1（现状一句话）

个人技术成长 Companion：**聊天是表面，验证是核心闭环**；Critic + 确定性门写回掌握；REST↔MCP 共享 `db.ops`。

### V2（升级后是什么）

**Gotit = Personal Mastery Agent Runtime**

面向长期学习状态的 **AI Native 运行时**。核心不是「多几个 Agent 角色」，而是：

```text
LearnerState（权威状态投影）
    ↑ writeback（唯一写入口）
Agent Run（plan → execute → evaluate → commit/abort）
    ↑ tools（副作用分级 + 可观测）
Evidence Pack（预算化上下文，非整库塞 prompt）
    ↑ eval harness（改动必须有 holdout 证据）
```

**对外一句话（面试用）：**

> 我做了一个把「会不会」做成系统契约的 Agent 应用：模型可以出题、讲解、调工具，但掌握档位、排程、失败图写回都由确定性运行时裁决；并且用 harness 把 prompt/skill 演进变成可回归工程。

**刻意不做的 V2：**

- 第二大脑 / 通用 RAG 产品化
- 多租户 Agent 平台
- 为展示而 Multi-Agent 编排
- 用 LLM 替代 gate
- 自动挂载全量 MCP 进聊天

---

## 2. 核心架构升级

### 2.1 逻辑视图

```text
┌─────────────────────────────────────────────────────────────┐
│                     Surfaces (非核心)                        │
│   Web Chat / MCP(OpenClaw) / Skills                          │
└──────────────────────────┬──────────────────────────────────┘
                           │ 同一 Run API
┌──────────────────────────▼──────────────────────────────────┐
│                 Agent Runtime (core)                         │
│  RunLifecycle: intent → plan → execute → evaluate → commit  │
│  BallCustody / VerifyWorkflow 升级为通用 RunState            │
│  Policy: 哪些 step 可调 LLM / 哪些必须 code                  │
└─┬──────────────┬──────────────┬──────────────┬──────────────┘
  │              │              │              │
  ▼              ▼              ▼              ▼
┌──────┐   ┌──────────┐   ┌─────────┐   ┌──────────────┐
│Tool  │   │ Memory   │   │ State   │   │ Evaluation   │
│Layer │   │ Layer    │   │ Mgmt    │   │ Layer        │
└──────┘   └──────────┘   └─────────┘   └──────────────┘
```

### 2.2 Agent Runtime

**现状缺口：** Verify 有 `VerifyWorkflow` / `BallCustody`；Chat 有 `chat_orchestrator` + tool whitelist——两套「跑法」，缺少统一 Run 生命周期与 commit 边界。

**V2 设计：**

```text
AgentRun
  run_id, kind ∈ {chat, examine, teach, calibrate, ingest, close_day}
  stage ∈ {plan, execute, evaluate, commit, aborted}
  ball / custody（可序列化）
  tool_trace[]
  eval_trace[]
  proposed_writes[]   ← 未 commit 前不可落库权威状态
```

**硬规则：**

1. LLM 输出只能进入 `proposed_*`，不能直接写 Claim mastery
2. `commit` 只走现有权威路径：`write_mastery_outcome` / graph ops / schedule
3. Chat tool 的 `start_*` 继续是 **prepare-only**（与现网一致）——Runtime 显式编码，不靠约定

**目标形态：**

```text
Planning（决定 kind / claim / tools 子集）
  → Execution（LLM ± tools，只产 traces + proposals）
  → Evaluation（Critic / gate / routing / policy checks）
  → State Update（唯一 Committer）
```

**面试点：** Production Agent ≠ `while(tool)`；而是有状态机、有 abort、有写事务边界。

### 2.3 Memory Layer

**现状缺口：** 权威已分散正确（claim / fail_events / graph vs `memory_entries`），但缺显式 **Learner State Model**；叙事仍易被理解成「有聊天记忆」。

**V2：分层记忆（不是向量库优先）**

| 层 | 存什么 | 权威？ | 注入方式 |
|----|--------|--------|----------|
| **L0 Working** | 本 run 的 claim、答案、tool 结果 | 临时 | 全量进本 run |
| **L1 Episodic** | verify trajectory、fail_events | 是（事件） | top-k + 预算 |
| **L2 Semantic LearnerState** | θ/弱点簇、易混对、due 原因、lane | **派生权威** | 结构化块，非散文 |
| **L3 Preference/Shell** | bootcamp/prefs/interest | 是（产品） | 极少注入模型 |
| **L4 Raw notes** | 笔记全文 | 素材，非掌握 | **默认不进**；仅 ingest/出题时 |

**关键升级：** 从「聊天记录 = 记忆」→ **LearnerStateSnapshot（可版本、可 diff、可解释）**

```text
LearnerStateSnapshot
  as_of
  owed_summary          # due_reason 聚合
  weak_clusters[]       # 来自 graph + fail severity
  active_confusions[]   # confused_with
  failure_lessons[]     # digest cache，带 TTL/去重
  interview_lane
  context_fingerprint   # 用于 eval 复现
```

**为什么不是先做 RAG：** 掌握问题是 **状态与证据**，不是「找相似段落」。RAG 最多服务 ingest/深挖检索；不能当 mastery memory。

### 2.4 State Management

**现状强项：** `state-boundary-tighten` 已接近正确模型。

**V2 补齐工程可叙述契约：**

```text
WritePlane
  AUTHORITATIVE: claim mastery, next_review, fail_events, graph_edges
  DERIVED:       failure_digest, mastery_snapshot, brief owed
  AUDIT:         trajectory steps, tool_calls metadata, harness decisions
  EPHEMERAL:     run working memory, LLM scratch
```

**系统级能力（非 UI）：**

1. **Write Intent → Commit**：Runtime 产出 `WriteIntent`，单一 `StateCommitter` 执行
2. **Idempotent keys**：同 claim+verdict digest、同 run commit 可重放
3. **Replay**：给定 `run_id` 能重放 evaluate+commit（LLM 可 stub）

### 2.5 Tool Layer

**现状：** companion builtin whitelist（正确方向）。

**V2：Tool 作为策略对象，不是函数列表**

```text
ToolSpec
  name, args_schema
  side_effect ∈ {read, prepare, write_derived, write_authoritative}
  allowed_run_kinds
  requires_confirm?     # prepare→open CTA 可视为 confirm
  summary_policy        # 进 metadata 的摘要规则
```

**策略：**

- Chat Runtime **禁止** `write_authoritative`（过门只走 finalize）
- Examine/Teach finalize 是 **系统工具**，不是模型可随意调用的 MCP 全集
- 观测：每次 tool call → `ToolTrace(ok, latency, args_digest, effect_class)`

**不做：** 自动挂载全量 gotit MCP 进聊天。

### 2.6 Evaluation Layer

**现状：** harness + metric rollups + human `adopt|observe|reject`（审计，不自动改 prompt）。

**V2：Eval 升为一等闭环**

```text
Change Candidate (prompt/skill/routing/budget)
    → Offline suite (dev/gold + holdout)
    → Metrics gate (gate_consistent, routing_ok, no_spurious_write, …)
    → Decision (observe/adopt/reject)
    → If adopt: version pin + changelog（仍可人工 apply）
    → Regression on next PR via gate.sh
```

**工程增量：**

1. **Holdout split 硬编码**（VISION P5）
2. **Agent Run Replay harness**：固定 stub LLM，断言 write intents
3. **Eval fixtures = LearnerState 快照**，不只是字符串 case

---

## 3. P0 必须建设

> 每项必须回答：为什么需要 / 解决什么 AI 系统问题 / 体现什么工程能力 / 技术方案。

### P0-1 Memory Architecture → Learner State Model

| 问 | 答 |
|----|----|
| **为什么需要？** | 聊天记录与 `memory_entries` 不能回答「今天为何欠练 / 曾栽在哪」；权威已在 claim/graph，但缺统一状态投影。 |
| **解决什么 AI 系统问题？** | 长期状态 vs 短期上下文；防 memory dump；防模型散文覆盖结构化真相。 |
| **体现什么工程能力？** | Memory taxonomy、write authority、derived cache、可版本快照。 |
| **技术方案** | 在 `core` 定义 `LearnerStateSnapshot` + builder（只读聚合 claim/due/graph/lessons）；所有 agent prompt 组装只吃 Snapshot + ContextBudget；禁止直接拼 raw notes/chat。 |

**可测交付：** `build_learner_state(as_of) -> Snapshot`；snapshot 进 examine/chat 注入；单测断言「passed 后 owed 变化」不依赖 LLM。

### P0-2 Agent Workflow → 统一 RunLifecycle

| 问 | 答 |
|----|----|
| **为什么需要？** | Chat 与 Verify 两套编排，副作用边界靠约定；扩展第 N 种 workflow 会再次分叉。 |
| **解决什么 AI 系统问题？** | Agent 不可控副作用、半失败态、无法 abort/replay。 |
| **体现什么工程能力？** | 状态机 Runtime、事务式 commit、LLM 输出与世界状态解耦。 |
| **技术方案** | 抽象 `AgentRun` / `RunLifecycle`；VerifyWorkflow 成为 `kind=examine\|teach` 的特化；chat_orchestrator 变为 `kind=chat` executor；`proposed_writes` 仅在 evaluate 通过后 commit。 |

**可测交付：** 一次 examine 可用 `run_id` 查出 plan/tool/eval/commit；重复 commit 幂等。

### P0-3 Evaluation Loop → Holdout + Replay 硬化

| 问 | 答 |
|----|----|
| **为什么需要？** | 已有 harness 决策，但缺 holdout 与「无 LLM 可回归写回」；面试官会问 adopt 后如何不回退。 |
| **解决什么 AI 系统问题？** | Prompt drift、评测污染、无法复现的 agent 行为。 |
| **体现什么工程能力？** | Eval-driven development、metric contracts、CI 级 agent 回归。 |
| **技术方案** | ① holdout suite 与 gold 隔离；② Replay harness：stub LLM + 固定 Snapshot → 断言 `GateResult` / `WriteIntent` / `no_spurious_write`；③ `gate.sh` 接入 replay；adopt 仍人工，但必须绑定 suite 版本号。 |

**可测交付：** `scripts/run_replay_harness.py` + 至少 8–12 个 replay case（gate 降级、prepare-only 不写 mastery、failure lesson 注入预算、routing）。

### P0-4 Context Engineering 一等公民化

| 问 | 答 |
|----|----|
| **为什么需要？** | `ContextBudget` 已在 Axiom；其它 agent/chat 仍可能随意拼上下文。 |
| **解决什么 AI 系统问题？** | Context overflow、噪声压过证据、成本与质量不可控。 |
| **体现什么工程能力？** | Context packing、优先级裁剪、可观测 token/char 会计。 |
| **技术方案** | 统一 `EvidencePack` 编译器：输入 Snapshot → 有序 blocks（claim / confuse / lessons / plan / tools）→ Budget trim（先 lessons 后 graph，沿用现策略）→ 输出 `pack_hash` 供 eval 复现。 |

**可测交付：** 所有 LLM 入口只收 `EvidencePack`；trace 记录各 block 使用量与 trim 决策。

---

## 4. P1 增强能力

### P1-1 Tool Calling 硬化（策略 + 契约）

| 问 | 答 |
|----|----|
| **为什么需要？** | 白名单已有，但缺副作用分级与跨 surface 契约测试。 |
| **AI 问题** | Tool hallucination、越权写、不可审计。 |
| **工程能力** | Tool policy engine、effect classification、parity tests。 |
| **方案** | `ToolSpec` 注册表；chat 禁止 authoritative writes；REST/MCP/companion 三路共享同一 registry；契约测试：同 args → 同 effect class。 |

### P1-2 Agent Observability（Run Trace）

| 问 | 答 |
|----|----|
| **为什么需要？** | 现有 bubble tool trail 对用户友好，但对工程调试/评测不够。 |
| **AI 问题** | 黑盒 agent、无法归因失败（模型 vs 工具 vs 门）。 |
| **工程能力** | Tracing、structured logs、eval 关联。 |
| **方案** | `AgentTrace` 持久化（run_id, stages, tool_trace, gate signals, pack_hash, model ids）；CLI / `/v1/obs/runs/{id}` 只读；**不做**花哨监控产品页。 |

### P1-3 Knowledge Base（窄定义）≠ 通用 RAG

| 问 | 答 |
|----|----|
| **为什么需要？** | Ingest/出题需要从笔记取证；深挖需要项目材料定位。 |
| **AI 问题** | 检索噪声污染验证；「检索命中」被误当成「已掌握」。 |
| **工程能力** | Retrieval 与 Judgment 解耦。 |
| **方案** | **Claim-anchored retrieval**：只在 `ingest` / `drill` / `examine` 出题阶段检索 note chunks；检索结果进 EvidencePack 的 `source` block，**永不**单独写 mastery；可选轻量 chunk 表，不做开放域 QA。 |

P1 的 KB 是「验证素材索引」，不是第二大脑。

### P1-4 RAG（仅作为 KB 的实现细节）

| 问 | 答 |
|----|----|
| **为什么需要？** | 笔记变长后，全量塞 prompt 违反 VISION P4。 |
| **AI 问题** | 长上下文失效、成本爆炸。 |
| **工程能力** | Hybrid retrieval + budget；知道何时 **不该** RAG。 |
| **方案** | 先 keyword/结构（claim 绑定段落）→ 不够再 embedding；检索评分进 harness（「注入了无关段落」应失败）。 |

**面试话术：** 先证明无向量库也能正确；向量只是 scale 手段。

### P1-5 Context Engineering 深化

在 P0-4 之上：

- 按 `preferred_check_mode` 换 pack 配方（probe vs teach_back）
- 动态预算：Critic 用更短 pack（降相关噪声）
- A/B 由 harness 度量，不靠体感

---

## 5. P2 可选能力

### P2-1 Multi-Agent Orchestration（真编排，不是多角色）

**现状已有：** 多人格 + Critic 复核 + A2A handoff——这是 **角色分工**，不是 Multi-Agent 平台。

**何时才需要真 Multi-Agent：**

- 单 Run 内必须并行子任务（例如：出题 ∥ 检索 ∥ 排程建议），且要有合并策略
- 或 Supervisor 需要在多个可失败专家间做可审计路由

| 问 | 答 |
|----|----|
| **为什么需要？（仅当）** | 单 agent 上下文/工具集无法同时保证「出题质量」与「材料定位」且延迟可接受。 |
| **AI 问题** | 协调失败、责任不清、成本倍增。 |
| **工程能力** | Supervisor/worker、ball custody 跨 agent、合并冲突策略。 |
| **方案** | 扩展 BallCustody：`holder` + `stage`；worker 只返回 proposal；Supervisor 唯一可 commit；用 replay harness 锁行为。 |

**默认不做：** 当前瓶颈是状态 / 评测 / 上下文，不是 Agent 数量。堆 Multi-Agent 会被识破为炫技。

### P2-2 Auto-adopt prompt（强烈延后）

与 VISION P5 冲突风险高。最多做到：adopt 生成 PR 补丁草案，仍需人合并 + holdout 绿。

### P2-3 通用 Agent-as-Tool / 全 MCP 进 Chat

**不做。** 副作用面过大，破坏 prepare/finalize 边界。限制工具面是特性。

---

## 6. 开发优先级（1–2 个月）

评分：投入成本 ↓ / 技术收益 ↑ / 面试价值 ↑。

| 序 | 项 | 成本 | 收益 | 面试价值 | 建议窗口 |
|----|----|------|------|----------|----------|
| 1 | **P0-3 Eval Replay + Holdout** | 中 | 极高 | 极高 | Week 1–2 |
| 2 | **P0-1 LearnerStateSnapshot** | 中 | 极高 | 极高 | Week 1–3 |
| 3 | **P0-4 EvidencePack 统一** | 中低 | 高 | 高 | Week 2–3 |
| 4 | **P0-2 RunLifecycle 统一** | 高 | 极高 | 极高 | Week 3–6 |
| 5 | **P1-1 ToolSpec/Policy** | 中 | 高 | 高 | Week 5–7 |
| 6 | **P1-2 Run Trace Observability** | 中 | 高 | 高 | Week 6–8 |
| 7 | **P1-3/4 Claim-anchored KB/RAG** | 中高 | 中高 | 中（会讲边界则高） | Week 7–8 |
| 8 | **P2 Multi-Agent** | 高 | 条件收益 | 中（讲清前提才加分） | 仅当 P0 完成且有真实并行痛点 |

### 推荐节奏（8 周）

```text
W1–W2  Eval 硬化（replay + holdout + gate.sh）
       → 先有「防回退」能力，再敢改 Runtime

W2–W3  LearnerState + EvidencePack
       → 记忆与上下文从「拼字符串」变成「编译产物」

W3–W6  Agent RunLifecycle（chat/verify 收束）
       → 面试主故事成型：Plan→Exec→Eval→Commit

W6–W8  Tool policy + Trace
       → 补齐生产感；KB/RAG 仅 claim-anchored 薄做

不做   产品页、增长、Multi-Agent 平台、全量 RAG、auto-adopt
```

### 投入 / 收益示意

```text
面试价值
   ▲
高 │  Replay/Holdout ★   RunLifecycle ★   LearnerState ★
   │  EvidencePack ●     ToolPolicy ●     Trace ●
   │  Claim-KB ○
   │  Multi-Agent △（条件）
低 │  通用RAG/堆Agent ✕
   └──────────────────────────────────────────────► 投入
        低              中              高
```

---

## 7. V2 成功标准（工程验收，非 DAU）

1. **任意 mastery 写回** 都能追溯到一个 `run_id` + `WriteIntent` + gate signals
2. **改 prompt/skill** 必须过 holdout；replay 在 CI 红则不能合
3. **所有 LLM 调用** 只消费 `EvidencePack`（可打印 trim 决策）
4. **Chat 无法 authoritative write mastery**（契约测试锁死）
5. 面试 5 分钟能画清：LLM / Critic / Gate / State / Eval 的责任边界

---

## 8. 落地建议

- 实现时开 **一个** OpenSpec change（建议名 `agent-runtime-v2`），把 P0-1～P0-3 收成同一提案的 Phases；避免拆成互不咬合的「看起来很 AI」的文件夹。
- 改行为前同步 `docs/SYSTEM.md`；定位/准入冲突时先改 `docs/PRODUCT.md` / `docs/VISION.md`。
- 本文件是 **技术演进设计**，不是产品 backlog；主路径 UX 仍以 `openspec/changes/main-path-converge/` 为准。

---

## 9. 一句话总结

> **未来 1–2 个月：把 Gotit 从「验证型 Companion 应用」升级为「可评测、可回放、有状态权威的 Mastery Agent Runtime」——用 LearnerState + RunLifecycle + Eval Harness 证明 AI Native Engineering，而不是用更多页面或更多 Agent 角色证明会调 API。**
