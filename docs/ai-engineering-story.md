# Gotit — AI Engineering 故事（项目收敛 / 面试包装）

> 状态：**Phase 0–3 已落地**（2026-08-03）。Phase 4 可选。  
> 依据：`agent-runtime-roadmap.md`、`implementation-review.md`、  
> `openspec/changes/agent-runtime-v2/`、ADR-0003 / ADR-0004。  
> **勿过度宣称：** 聊天路径尚未消费 Snapshot / Pack；所谓 Runtime 是  
> **薄的 verify 信封**，不是统一多表面 Agent OS。

---

## 1. 最终架构（诚实版）

```text
┌─ 表面 ──────────────────────────────────────────────────────┐
│  Web ChatShell              MCP / OpenClaw（薄）              │
│  （prepare / 叙述）          → 同一套 db.ops                   │
└────────────┬───────────────────────────┬────────────────────┘
             │ REST                      │ MCP tools
             ▼                           ▼
┌─ API 编排 ──────────────────────────────────────────────────┐
│  chat_orchestrator（工具白名单，仅 prepare）                   │
│  examine / teach / verify_attempt → EvidencePack              │
│  verify_finalize：AgentRun → WriteIntent → gate → commit      │
└────────────┬────────────────────────────────────────────────┘
             ▼
┌─ gotit.core（无框架依赖）────────────────────────────────────┐
│  agents（axiom/critic/echo/…）→ 只产出提案                     │
│  LearnerStateSnapshot（派生）· EvidencePack（预算/hash）       │
│  AgentRun / WriteIntent / CommitReceipt                       │
│  deterministic_gate · schedule · context_budget               │
└────────────┬────────────────────────────────────────────────┘
             ▼
┌─ 权威 + 审计 ───────────────────────────────────────────────┐
│  权威：ClaimRow、计划、fail_events、graph_edges                 │
│  派生：failure_digest、LearnerStateSnapshot、Brief 欠练         │
│  审计：trajectory（+run_id/idempotency_key）、harness 决策      │
│  写口：write_mastery_outcome（掌握行唯一路径）                  │
└─────────────────────────────────────────────────────────────┘
             ▲
┌─ 评测 ──────────────────────────────────────────────────────┐
│  harness dev/gold + replay + holdout → gate.sh                 │
│  adopt 绑定 suite_version（仅审计，不自动改 prompt）           │
└─────────────────────────────────────────────────────────────┘
```

### 核心模块职责

| 模块 | 职责 |
|------|------|
| Chat / companion 工具 | 表面 + prepare CTA；**绝不**写掌握 |
| Examine / teach / verify_attempt | 装载 EvidencePack；跑角色 Agent；调用 finalize |
| `verify_finalize` | 信封：propose → evaluate → commit |
| `deterministic_gate` | 掌握**唯一裁决者**（代码） |
| `write_mastery_outcome` | 掌握**行**唯一写口 |
| `LearnerStateSnapshot` | 派生：欠练 / 弱簇 / 易混 / 教训 / 轻偏好 + fingerprint |
| `EvidencePack` | 预算化上下文 + `pack_hash`，供 verify LLM 调用 |
| Harness replay / holdout | 无真实 LLM 下锁住契约回归 |

### LLM vs Code 责任边界

| 关切 | 归属 |
|------|------|
| 出题 / 点评 / 聊天 / Critic 意见 | **LLM** |
| 掌握档位、排程、写回、CTA 路由 | **Code** |
| 提案进入 WriteIntent | **LLM → 信封** |
| 是否可 commit（`intent_may_commit`） | **Code** |
| 防污染 + 防回退证明 | **Harness / gate.sh** |

---

## 2. 为什么不是三类 Demo

| Demo 形态 | Gotit 的差异 |
|-----------|--------------|
| **ChatGPT Wrapper** | 聊天只是壳。流利文本不能伪造掌握。prepare ≠ finalize。无 API key 的 stub 不假写。Gate 是代码。 |
| **RAG Demo** | 权威在 claim / 排程 / 失败图**状态**，不是检索命中。上下文是 EvidencePack 预算编译；无向量库当掌握记忆。 |
| **Multi-Agent Demo** | 五角色 = **固定 Verify Spine 上的角色分工**，不是开放协作平台。自主度刻意短；状态迁移才是产品。 |

**最大技术亮点（一句）：**

> LLM 出证 → Critic 只能降级 → 确定性 Gate → 单一掌握写回；Snapshot / Pack 管上下文；Replay / Holdout 让 Agent 改动可进 CI 回归 —— **聊天是壳，掌握是真相。**

---

## 3. 简历最终版

**项目名称：** Gotit — Personal Mastery Agent Runtime  
（副标可用：以验证为中心的长期技术成长 Agent Application）

**四条 bullet：**

1. 设计以验证为中心的 Agent Application：多角色 LLM 仅产出 examine / recheck **提案**；确定性 Gate 与单一 `write_mastery_outcome` 独占过关与排程写回，避免模型单方面污染长期学习状态。  
2. 实现派生 **LearnerStateSnapshot** 与 **EvidencePack** 上下文管线（预算裁剪 + `pack_hash`）：再练注入失败教训与图邻接并受硬上限约束 —— 记忆是可排程的掌握态，而非聊天史或开放 RAG。  
3. 落地薄 **Verify Run 信封**（`AgentRun` / `WriteIntent` / `CommitReceipt`）：掌握提交走 propose → evaluate → commit，带 `run_id` 审计与同键幂等重提交 —— 生产 Agent 即带 abort / commit 边界的状态机。  
4. 将 **Replay + Holdout** 接入 CI（`gate.sh`），adopt 绑定 `suite_version`，在无真实 LLM 下锁住 gate / 写回 / prepare-only 契约，防止 prompt / 预算改动静默破坏防腐保证。

---

## 4. 五分钟面试介绍稿

**0:00–0:30 — 定位**  
Gotit 不是学习聊天机器人，而是个人掌握态 Agent Application：聊天管表面，**Verified = done**。工程论题是判断边界 —— LLM 生成，代码裁决。

**0:30–2:00 — 架构**  
画：表面 → verify 路径从派生 LearnerState 编译 EvidencePack → 角色 Agent 提案 → Critic 复核 → WriteIntent → deterministic_gate → write_mastery_outcome → trajectory 带 run_id。REST 与 MCP 共用同一套 ops。聊天工具仅 prepare。

**2:00–3:30 — 硬设计**  
为何 Gate 必须是代码（VISION）。为何 prepare ≠ finalize。为何失败是一等状态（图 + 教训）并按预算再注入。为何 Snapshot 只派生、不落第二张权威表。

**3:30–4:30 — 工程闭环**  
Replay / Holdout 进 gate.sh：既不污染掌握，也不过拟合 gold。Adopt 是人 + suite_version，不是自动改 prompt。这是 AI Native Engineering，不是功能堆砌。

**4:30–5:00 — 边界**  
刻意不做：通用 RAG、Multi-Agent 平台、LLM 当法官、全量 MCP 挂进聊天。那些会稀释 Verified = done。

---

## 5. 面试深挖 15 问 + 回答方向

1. **为何 Critic 不能单独过门？** — 双人取严 + 代码终审；Critic 信号只能降级。  
2. **「会了」的真相在哪？** — ClaimRow 状态 / 排程经 `write_mastery_outcome`，不是聊天或 memory_entries。  
3. **WriteIntent 干什么？** — 只装 LLM 提案；Gate 接受前无写权。  
4. **如何防止 tool-calling 伪造掌握？** — companion 白名单 prepare-only；契约测试 / replay。  
5. **算不算 Multi-Agent？** — 固定脊柱上的角色分工，不是开放 MAS。  
6. **为何不做 RAG？** — 掌握是状态 / 证据；检索 ≠ 过关。Pack 预算化 graph + lessons。  
7. **如何知道改 prompt 没有回退？** — CI 里 Replay + Holdout；adopt 钉 suite_version。  
8. **EvidencePack 买到什么？** — 统一编译、trim 策略、可复现 `pack_hash`。  
9. **LearnerStateSnapshot 是什么？** — 派生投影（ADR-0003）；重建，不当权威补丁。  
10. **run_id 有何用？** — 一次 finalize 信封关联掌握写 / trajectory；幂等键。  
11. **没有 LLM_API_KEY 时？** — stub；不伪造掌握升级。  
12. **REST 与 MCP 如何不漂移？** — 共享 `db.ops` + 同一 finalize。  
13. **为何不把聊天统一进同一 Runtime？** — 聊天不是写路径；verify-first 薄信封（ADR-0004）。  
14. **Drill / Sage？** — 仅预习；**不得**过门。  
15. **现在还弱在哪？** — 聊天未吃 Pack；无 ToolSpec / Trace 产品；outcome → policy 自调未做 —— 诚实下一层，防腐之后。

---

## 6. 后续建议（仅此）

### Phase 4 是否值得做？

**面试竞争力上非必须。** Phase 1–3 已够讲故事。Phase 4 是打磨（工具策略 + 只读 trace），不是新论点。

### 若做 Phase 4，只做：

1. 形式化 companion `ToolSpec.side_effect` + 契约测试（聊天禁止权威写）。  
2. 通过 CLI 或薄只读 API 暴露**已有**信封字段（`run_id` / pack_hash / receipt）—— **不做**监控产品页。  
3. 改动保持极小；做完归档 `agent-runtime-v2`。

### 明确不要做：

- 大一统 chat + verify Runtime 重写  
- Multi-Agent 平台 / 全量 MCP 进聊天  
- 通用 RAG / Learner 权威表  
- LLM-as-gate / auto-adopt  
- 为 Demo 改 Gate / 排程阈值  
- 借「AI Eng」名义堆新的产品 UX 波次  

**面试姿态：** 把 Phase 0–3 讲清楚；Phase 4 当可选附录，不是上桌门槛。
